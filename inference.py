"""Run model inference and save outputs for analysis"""
import os
import hydra
from omegaconf import DictConfig

from tqdm import tqdm
import numpy as np
import torch

from data.datasets import BrainInterSubject3DEval
from model.baselines import Identity, MirtkFFD, AntsSyN
# from lightning import LightningDLReg
from model.transformations import spatial_transform
from utils.image_io import save_nifti
from utils.misc import setup_dir

from analyse import analyse_output

import random
# seed RNG of eval dataset to get the same pairings for fair comparison
random.seed(7)


def get_inference_model(cfg):
    if cfg.model_type == 'dl':
        # TODO: DL model load model checkpoint; 2) eval mode; 3)put on GPU
        # model = LightningDLReg(hparams=cfg)
        pass

    elif cfg.model_type == 'baseline':
        if cfg.baseline.name == 'Id':
            model = Identity(cfg.dim)

        elif cfg.baseline.name == 'MIRTK':
            model = MirtkFFD(hparams=cfg.baseline.mirtk_params)

        elif cfg.baseline.name == 'ANTs':
            model = AntsSyN(hparams=cfg.baseline.ants_params)

        else:
            raise ValueError(f"Unknown baseline: {cfg.baseline.name}")

    else:
        raise ValueError(f"Unknown model_name: {cfg.model_type}")
    return model


def inference(model, inference_dataset, output_dir, device=torch.device('cpu')):
    print("Running inference:")

    for idx, batch in enumerate(tqdm(inference_dataset)):
        # reshape data for inference.yaml
        for k, x in batch.items():
            # images 2d: (N, 1, H, W), 3d: (1, 1, H, W, D)
            # dvf 2d: (N, 2, H, W), 3d: (1, 3, H, W, D)
            if k != 'dvf_gt':
                batch[k] = x.unsqueeze(1).to(device=device)

        # model inference
        batch['dvf_pred'] = model(batch['target'], batch['source'])

        # deform source segmentation with predicted DVF
        if 'source_seg' in batch.keys():
            # apply estimated transformation to segmentation
            batch['warped_source_seg'] = spatial_transform(batch['source_seg'], batch['dvf_pred'],
                                                           interp_mode='nearest')

        # deform source image with predicted DVF
        batch['warped_source'] = spatial_transform(batch['source'], batch['dvf_pred'])

        # deform target original image with predicted DVF
        if 'target_original' in batch.keys():
            batch['target_pred'] = spatial_transform(batch['target_original'], batch['dvf_pred'])

        # save the outputs
        subj_id = inference_dataset.subject_list[idx]

        output_id_dir = setup_dir(output_dir + f'/{subj_id}')
        for k, x in batch.items():
            x = x.detach().cpu().numpy()
            x = np.moveaxis(x, [0, 1], [-2, -1]).squeeze()
            save_nifti(x, path=output_id_dir + f'/{k}.nii.gz')


@hydra.main(config_path="conf", config_name="config_inference")
def main(cfg: DictConfig) -> None:
    print(cfg.pretty())

    # configure GPU
    gpu = cfg.gpu
    if gpu is not None and isinstance(gpu, int):
        os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu)
        device = torch.device('cuda')
    else:
        device = torch.device('cpu')

    # configure dataset & model
    inference_dataset = BrainInterSubject3DEval(**cfg.data)
    model = get_inference_model(cfg)

    # run inference
    output_dir = setup_dir(os.getcwd() + '/outputs')
    inference(model, inference_dataset, output_dir, device=device)

    # (optional) run analysis on the current inference outputs
    if cfg.analyse:
        analyse_output(output_dir, os.getcwd() + '/analysis', cfg.metric_groups)


if __name__ == '__main__':
    main()