"""Visualisation"""
import cv2
import imageio
import matplotlib
import numpy as np
import os
import random
from matplotlib import pyplot as plt

from utils.image_io import save_gif, save_png
from utils.metrics import computeJacobianDeterminant2D


def flow_to_hsv(opt_flow, max_mag=0.1, white_bg=False):
    """
    Encode optical flow to HSV.

    Args:
        opt_flow: 2D optical flow in (dx, dy) encoding, shape (H, W, 2)
        max_mag: flow magnitude will be normalised to [0, max_mag]

    Returns:
        hsv_flow_rgb: HSV encoded flow converted to RGB (for visualisation), same shape as input

    """
    # convert to polar coordinates
    mag, ang = cv2.cartToPolar(opt_flow[..., 0], opt_flow[..., 1])

    # hsv encoding
    hsv_flow = np.zeros((opt_flow.shape[0], opt_flow.shape[1], 3))
    hsv_flow[..., 0] = ang*180/np.pi/2  # hue = angle
    hsv_flow[..., 1] = 255.0  # saturation = 255
    hsv_flow[..., 2] = 255.0 * mag / max_mag
    # (wrong) hsv_flow[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)

    # convert hsv encoding to rgb for visualisation
    # ([..., ::-1] converts from BGR to RGB)
    hsv_flow_rgb = cv2.cvtColor(hsv_flow.astype(np.uint8), cv2.COLOR_HSV2BGR)[..., ::-1]
    hsv_flow_rgb = hsv_flow_rgb.astype(np.uint8)

    if white_bg:
        hsv_flow_rgb = 255 - hsv_flow_rgb

    return hsv_flow_rgb


def blend_image_seq(images1, images2, alpha=0.7):
    """
    Blend two sequences of images.
    (used in this project to blend HSV-encoded flow with image)
    Repeat to fill RGB channels if needed.

    Args:
        images1: numpy array, shape (H, W, Ch, Frames) or (H, W, Frames)
        images2: numpy array, shape (H, W, Ch, Frames) or (H, W, Frames)
        alpha: mixing weighting, higher alpha increase image 2.  (1 - alpha) * images1 + alpha * images2

    Returns:
        blended_images: numpy array, shape (H, W, Ch, Frames)
    """
    if images1.ndim < images2.ndim:
        images1 = np.repeat(images1[:, :, np.newaxis, :], images2.shape[2], axis=2)
    elif images1.ndim > images2.ndim:
        images2 = np.repeat(images2[:, :, np.newaxis, :], images1.shape[2], axis=2)

    assert images1.shape == images2.shape, "Blending: images being blended have different shapes, {} vs {}".format(images1.shape, images2.shape)
    blended_images = (1 - alpha) * images1 + alpha * images2

    return blended_images.astype(np.uint8)


def save_flow_hsv(op_flow, background, save_result_dir, fps=20, max_mag=0.1):
    """
    Save HSV encoded optical flow overlayed on background image.
    GIF and PNG images

    Args:
        op_flow: numpy array of shape (N, H, W, 2)
        background: numpy array of shape (N, H, W)
        save_result_dir: path to save result dir
        fps: frames per second, for gif
        max_mag: maximum flow magnitude used in normalisation

    Returns:

    """

    # encode flow in hsv
    op_flow_hsv = []
    for fr in range(op_flow.shape[0]):
        op_flow_hsv += [flow_to_hsv(op_flow[fr, :, :, :], max_mag=max_mag)]  # a list of N items each shaped (H, W, ch)

    # save flow sequence into a gif file and a sequence of png files
    op_flow_hsv = np.array(op_flow_hsv).transpose(1, 2, 3, 0)  # (H, W, 3, N)

    # overlay on background images
    op_flow_hsv_blend = blend_image_seq(background.transpose(1, 2, 0), op_flow_hsv)

    # save gif and png
    save_result_dir = os.path.join(save_result_dir, 'hsv_flow')
    if not os.path.exists(save_result_dir):
        os.makedirs(save_result_dir)
    save_gif(op_flow_hsv, os.path.join(save_result_dir, 'flow.gif'), fps=fps)
    save_gif(op_flow_hsv_blend, os.path.join(save_result_dir, 'flow_blend.gif'), fps=fps)
    save_png(op_flow_hsv_blend, save_result_dir)
    print("HSV flow saved to: {}".format(save_result_dir))


def save_flow_quiver(op_flow, background, save_result_dir, scale=1, interval=3, fps=20):
    """
    Plot quiver plot and save.

    Args:
        op_flow: numpy array of shape (N, H, W, 2)
        background: numpy array of shape (N, H, W)
        save_result_dir: path to save result dir

    Returns:
    """

    # set up saving directory
    save_result_dir = os.path.join(save_result_dir, 'quiver')
    if not os.path.exists(save_result_dir):
        os.makedirs(save_result_dir)

    # create mesh grid of vector origins
    # note: numpy uses x-y order in generating mesh grid, i.e. (x, y) = (w, h)
    mesh_x, mesh_y = np.meshgrid(range(0, background.shape[1]-1, interval), range(0, background.shape[2]-1, interval))

    png_list = []
    for fr in range(background.shape[0]):
        fig, ax = plt.subplots(figsize=(5, 5))
        ax = plt.imshow(background[fr, :, :], cmap='gray')
        ax = plt.quiver(mesh_x, mesh_y,
                        op_flow[fr, mesh_y, mesh_x, 1], op_flow[fr, mesh_y, mesh_x, 0],
                        angles='xy', scale_units='xy', scale=scale, color='g')
        save_path = os.path.join(save_result_dir, 'frame_{}.png'.format(fr))
        plt.axis('off')
        fig.savefig(save_path, bbox_inches='tight')
        plt.close(fig)

        # read it back to make gif
        png_list += [imageio.imread(save_path)]

    # save gif
    imageio.mimwrite(os.path.join(save_result_dir, 'quiver.gif'), png_list, fps=fps)
    print("Flow quiver plots saved to: {}".format(save_result_dir))


def save_warp_n_error(warped_source, target, source, save_result_dir, fps=20):
    """
    Calculate warping and save results

    Args:
        warped_source: source images warped to target images, numpy array shaped (N, H, W)
        target: target image, numpy array shaped (N, H, W)
        source: numpy array shaped (N, H, W)
        save_result_dir: numpy array shaped (N, H, W)
        fps:

    Returns:

    """

    # transpose all to (H, W, N)
    warped_source = warped_source.transpose(1, 2, 0)
    target = target.transpose(1, 2, 0)
    source = source.transpose(1, 2, 0)

    # calculate error normalised to (0, 255)
    error = np.abs(warped_source - target)
    error_before = np.abs(source - target)

    save_gif(error, os.path.join(save_result_dir, 'error.gif'), fps=fps)
    save_gif(error_before, os.path.join(save_result_dir, 'error_before.gif'), fps=fps)
    save_gif(target, os.path.join(save_result_dir, 'target.gif'), fps=fps)
    save_gif(warped_source, os.path.join(save_result_dir, 'wapred_source.gif'), fps=fps)
    save_gif(source, os.path.join(save_result_dir, 'source.gif'), fps=fps)
    print("Warping and error saved to: {}".format(save_result_dir))


def show_warped_grid(ax, dvf, bg_img, interval=3, title="Grid", fontsize=20):
    """dvf shape (2, H, W)"""
    background = bg_img
    interval = interval
    id_grid_X, id_grid_Y = np.meshgrid(range(0, bg_img.shape[0]-1, interval),
                                       range(0, bg_img.shape[1]-1, interval))

    new_grid_X = id_grid_X + dvf[1, id_grid_Y, id_grid_X]
    new_grid_Y = id_grid_Y + dvf[0, id_grid_Y, id_grid_X]

    kwargs = {"linewidth": 1.5, "color": 'c'}
    for i in range(new_grid_X.shape[0]):
        ax.plot(new_grid_X[i,:], new_grid_Y[i,:], **kwargs)  # each draw a line
    for i in range(new_grid_X.shape[1]):
        ax.plot(new_grid_X[:,i], new_grid_Y[:,i], **kwargs)

    ax.set_title(title, fontsize=fontsize)
    ax.imshow(background, cmap='gray')
    ax.axis('off')


def plot_results(target, source, warped_source, dvf, save_path=None, title_font_size=20, show_fig=False, dpi=100):
    """Plot all motion related results in a single figure
    dvf is expected to be in number of pixels"""

    # convert flow into HSV flow with white background
    hsv_flow = flow_to_hsv(dvf, max_mag=0.15, white_bg=True)

    ## set up the figure
    fig = plt.figure(figsize=(30, 18))
    title_pad = 10

    # source
    ax = plt.subplot(2, 4, 1)
    plt.imshow(source, cmap='gray')
    plt.axis('off')
    ax.set_title('Source', fontsize=title_font_size, pad=title_pad)

    # warped source
    ax = plt.subplot(2, 4, 2)
    plt.imshow(warped_source, cmap='gray')
    plt.axis('off')
    ax.set_title('Warped Source', fontsize=title_font_size, pad=title_pad)

    # calculate the error before and after reg
    error_before = target - source
    error_after = target - warped_source

    # error before
    ax = plt.subplot(2, 4, 3)
    plt.imshow(error_before, vmin=-255, vmax=255, cmap='gray')
    plt.axis('off')
    ax.set_title('Error before', fontsize=title_font_size, pad=title_pad)

    # error after
    ax = plt.subplot(2, 4, 4)
    plt.imshow(error_after, vmin=-255, vmax=255, cmap='gray')
    plt.axis('off')
    ax.set_title('Error after', fontsize=title_font_size, pad=title_pad)

    # target image
    ax = plt.subplot(2, 4, 5)
    plt.imshow(target, cmap='gray')
    plt.axis('off')
    ax.set_title('Target', fontsize=title_font_size, pad=title_pad)

    # hsv flow
    ax = plt.subplot(2, 4, 7)
    plt.imshow(hsv_flow)
    plt.axis('off')
    ax.set_title('HSV', fontsize=title_font_size, pad=title_pad)

    # quiver, or "Displacement Vector Field" (DVF)
    ax = plt.subplot(2, 4, 6)
    interval = 3  # interval between points on the grid
    background = source
    quiver_flow = np.zeros_like(dvf)
    quiver_flow[:, :, 0] = dvf[:, :, 0]
    quiver_flow[:, :, 1] = dvf[:, :, 1]
    mesh_x, mesh_y = np.meshgrid(range(0, dvf.shape[1] - 1, interval),
                                 range(0, dvf.shape[0] - 1, interval))
    plt.imshow(background[:, :], cmap='gray')
    plt.quiver(mesh_x, mesh_y,
               quiver_flow[mesh_y, mesh_x, 1], quiver_flow[mesh_y, mesh_x, 0],
               angles='xy', scale_units='xy', scale=1, color='g')
    plt.axis('off')
    ax.set_title('DVF', fontsize=title_font_size, pad=title_pad)

    # det Jac
    ax = plt.subplot(2, 4, 8)
    jac_det, mean_grad_detJ, negative_detJ = computeJacobianDeterminant2D(dvf)
    spec = [(0, (0.0, 0.0, 0.0)), (0.000000001, (0.0, 0.2, 0.2)),
            (0.12499999999, (0.0, 1.0, 1.0)), (0.125, (0.0, 0.0, 1.0)),
            (0.25, (1.0, 1.0, 1.0)), (0.375, (1.0, 0.0, 0.0)),
            (1, (0.94509803921568625, 0.41176470588235292, 0.07450980392156863))]
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list('detjac', spec)
    plt.imshow(jac_det, vmin=-1, vmax=7, cmap=cmap)
    plt.axis('off')
    ax.set_title('Jacobian (Grad: {0:.2f}, Neg: {1:.2f}%)'.format(mean_grad_detJ, negative_detJ * 100),
                 fontsize=int(title_font_size*0.9), pad=title_pad)
    # split and extend this axe for the colorbar
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    divider = make_axes_locatable(ax)
    cax1 = divider.append_axes("right", size="5%", pad=0.05)
    cb = plt.colorbar(cax=cax1)
    cb.ax.tick_params(labelsize=20)

    # adjust subplot placements and spacing
    plt.subplots_adjust(left=0.0001, right=0.99, top=0.9, bottom=0.1, wspace=0.001, hspace=0.1)

    # saving
    if save_path is not None:
        fig.savefig(save_path, bbox_inches='tight', dpi=dpi)

    if show_fig:
        plt.show()
    plt.close()


def save_train_result(target, source, warped_source, dvf, save_result_dir, epoch, fps=20, dpi=40):
    """
    Args:
        target: (N, H, W)
        source: (N, H, W)
        warped_source: (N, H, W)
        dvf: (N, H, W, 2)
        save_result_dir:
        epoch:
        fps:

    Returns:

    """
    # loop over time frames
    png_buffer = []
    for fr in range(dvf.shape[0]):
        dvf_fr = dvf[fr, :, :, :]  # (H, W, 2)
        target_fr = target[fr, :, :]  # (H, W)
        source_fr = source[fr, :, :]  # (H, W)
        warped_source_fr = warped_source[fr, :, :]  # (H, W)

        fig_save_path = os.path.join(save_result_dir, f'frame_{fr}.png')
        plot_results(target_fr, source_fr, warped_source_fr, dvf_fr, save_path=fig_save_path, dpi=dpi)

        # read back the PNG to save a GIF animation
        png_buffer += [imageio.imread(fig_save_path)]
        os.remove(fig_save_path)
    imageio.mimwrite(os.path.join(save_result_dir, f'epoch_{epoch}.gif'), png_buffer, fps=fps)


def plot_results_t1t2(vis_data_dict, save_path=None, title_font_size=20, show_fig=False, dpi=100):
    """Plot all motion related results in a single figure
    dvf is expected to be in number of pixels"""

    ## set up the figure
    fig = plt.figure(figsize=(30, 18))
    title_pad = 10

    ax = plt.subplot(2, 4, 1)
    plt.imshow(vis_data_dict["target"], cmap='gray')
    plt.axis('off')
    ax.set_title('Target (T1-syn)', fontsize=title_font_size, pad=title_pad)

    ax = plt.subplot(2, 4, 2)
    plt.imshow(vis_data_dict["target_original"], cmap='gray')
    plt.axis('off')
    ax.set_title('Target original (T1)', fontsize=title_font_size, pad=title_pad)

    # calculate the error before and after reg
    error_before = vis_data_dict["target"] - vis_data_dict["target_original"]
    error_after = vis_data_dict["target"] - vis_data_dict["target_pred"]

    # error before
    ax = plt.subplot(2, 4, 3)
    plt.imshow(error_before, vmin=-2, vmax=2, cmap='gray')  # assuming images were normalised to [0, 1]
    plt.axis('off')
    ax.set_title('Error before', fontsize=title_font_size, pad=title_pad)

    # error after
    ax = plt.subplot(2, 4, 4)
    plt.imshow(error_after, vmin=-2, vmax=2, cmap='gray')  # assuming images were normalised to [0, 1]
    # plt.imshow(error_after, cmap='gray')
    plt.axis('off')
    ax.set_title('Error after', fontsize=title_font_size, pad=title_pad)

    ax = plt.subplot(2, 4, 5)
    plt.imshow(vis_data_dict["target_pred"], cmap='gray')
    plt.axis('off')
    ax.set_title('Target predict', fontsize=title_font_size, pad=title_pad)

    ax = plt.subplot(2, 4, 6)
    plt.imshow(vis_data_dict["warped_source"], cmap='gray')
    plt.axis('off')
    ax.set_title('Warped source', fontsize=title_font_size, pad=title_pad)

    # deformed grid ground truth
    ax = plt.subplot(2, 4, 7)
    bg_img = np.zeros_like(vis_data_dict["target"])
    show_warped_grid(ax, vis_data_dict["dvf_gt"], bg_img, interval=3, title="$\phi_{GT}$", fontsize=title_font_size)

    ax = plt.subplot(2, 4, 8)
    show_warped_grid(ax, vis_data_dict["dvf_pred"], bg_img, interval=3, title="$\phi_{pred}$", fontsize=title_font_size)

    # # hsv flow
    # # convert flow into HSV flow with white background
    # hsv_flow = flow_to_hsv(vis_data_dict["dvf"], max_mag=0.15, white_bg=True)
    # todo: DVF shape change to be applied
    # ax = plt.subplot(2, 4, 7)
    # plt.imshow(hsv_flow)
    # plt.axis('off')
    # ax.set_title('HSV', fontsize=title_font_size, pad=title_pad)

    # # quiver, or "Displacement Vector Field" (DVF)
    # todo: DVF shape change to (2, H, W) to be applied
    # ax = plt.subplot(2, 4, 6)
    # interval = 3  # interval between points on the grid
    # background = source
    # quiver_flow = np.zeros_like(dvf)
    # quiver_flow[:, :, 0] = dvf[:, :, 0]
    # quiver_flow[:, :, 1] = dvf[:, :, 1]
    # mesh_x, mesh_y = np.meshgrid(range(0, dvf.shape[1] - 1, interval),
    #                              range(0, dvf.shape[0] - 1, interval))
    # plt.imshow(background[:, :], cmap='gray')
    # plt.quiver(mesh_x, mesh_y,
    #            quiver_flow[mesh_y, mesh_x, 1], quiver_flow[mesh_y, mesh_x, 0],
    #            angles='xy', scale_units='xy', scale=1, color='g')
    # plt.axis('off')
    # ax.set_title('DVF', fontsize=title_font_size, pad=title_pad)

    # # det Jac
    # ax = plt.subplot(2, 4, 8)
    # todo: DVF shape change to (2, H, W) to be applied
    # jac_det, mean_grad_detJ, negative_detJ = computeJacobianDeterminant2D(dvf)
    # spec = [(0, (0.0, 0.0, 0.0)), (0.000000001, (0.0, 0.2, 0.2)),
    #         (0.12499999999, (0.0, 1.0, 1.0)), (0.125, (0.0, 0.0, 1.0)),
    #         (0.25, (1.0, 1.0, 1.0)), (0.375, (1.0, 0.0, 0.0)),
    #         (1, (0.94509803921568625, 0.41176470588235292, 0.07450980392156863))]
    # cmap = matplotlib.colors.LinearSegmentedColormap.from_list('detjac', spec)
    # plt.imshow(jac_det, vmin=-1, vmax=7, cmap=cmap)
    # plt.axis('off')
    # ax.set_title('Jacobian (Grad: {0:.2f}, Neg: {1:.2f}%)'.format(mean_grad_detJ, negative_detJ * 100),
    #              fontsize=int(title_font_size*0.9), pad=title_pad)
    # # split and extend this axe for the colorbar
    # from mpl_toolkits.axes_grid1 import make_axes_locatable
    # divider = make_axes_locatable(ax)
    # cax1 = divider.append_axes("right", size="5%", pad=0.05)
    # cb = plt.colorbar(cax=cax1)
    # cb.ax.tick_params(labelsize=20)

    # adjust subplot placements and spacing
    plt.subplots_adjust(left=0.0001, right=0.99, top=0.9, bottom=0.1, wspace=0.001, hspace=0.1)

    # saving
    if save_path is not None:
        fig.savefig(save_path, bbox_inches='tight', dpi=dpi)

    if show_fig:
        plt.show()
    plt.close()


def save_val_visual_results(data_dict, save_result_dir, epoch, dpi=50):
    """
    Save 1 random slice from N-slice stack (not a sequence)
    Args:
        data_dict: (dict, data shape (N, ch, *dims) {"target":,
                                                    "source":,
                                                    "warped_source":,
                                                    "target_original":,
                                                    "dvf_pred":,
                                                    "dvf_gt":}
        save_result_dir:
        epoch:
        dpi: image resolution
    """
    z = random.randint(0, data_dict["target"].shape[0]-1)

    vis_data_dict = {}
    for name in ["target", "source", "warped_source", "target_original", "target_pred"]:
        vis_data_dict[name] = data_dict[name][z, 0, ...]  # (*dims)

    for name in ["dvf_pred", "dvf_gt"]:
        vis_data_dict[name] = data_dict[name][z, ...]  # (dim, *dims)

    fig_save_path = os.path.join(save_result_dir, f'epoch{epoch}_slice_{z}.png')
    plot_results_t1t2(vis_data_dict, save_path=fig_save_path, dpi=dpi)