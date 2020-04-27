#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 17 17:20:07 2020

@author: petrapoklukar
"""

from __future__ import print_function
import os
from importlib.machinery import SourceFileLoader
import numpy as np
# from architectures.VAE_TinyResNet import VAE_TinyResNet as vae_m
from architectures.VAE_Conv2D_v2 import VAE_Conv2D_v2 as vae_m
from architectures.Classifier import Classifier as classifier_m
import torch
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import causal_utils as caus_utils
import itertools
import csv
import collections

def init_vae(opt, load_c=False):
    """Initialises the VAE model."""
    try:
        if load_c:
            checkpoint = torch.load(opt['exp_dir'] + '/vae_checkpoint199.pth', map_location=opt['device'])
            trained_dict = checkpoint['model_state_dict']
        else:
            print('CAUSALLLLLLLLLLAHFIUEGFUASDGFJAHSDGF(/FHkjsf')
            trained_dict = torch.load(opt['exp_dir'] + '/vae_model.pt', map_location=opt['device'])
        instance = vae_m(opt).to(opt['device'])
        instance.load_state_dict(trained_dict)
        return instance
    except:
        raise NotImplementedError(
                'Model {0} not recognized'.format(opt['model']))
        
def init_classifier(opt):
    """Initialises the classifier."""
    try:
        instance = classifier_m(opt).to(opt['device'])
        trained_dict = torch.load(opt['exp_dir'] + '/classifier_model.pt', map_location=opt['device'])
        instance.load_state_dict(trained_dict)
        return instance
    except:
        raise NotImplementedError(
                'Model {0} not recognized'.format(opt['model']))
        
        
def get_config(exp_name, key='vae_opt'):
    config_file = os.path.join('.', 'configs', exp_name + '.py')
    directory = os.path.join('.', 'models', exp_name)
    model_config = SourceFileLoader(exp_name, config_file).load_module().config 
    model_config['exp_name'] = exp_name
    model_config[key]['exp_dir'] = directory 
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model_config['device'] = device
    model_config[key]['device'] = device
    return model_config


            
def sample_prior(ld, n_samples, vae, classifier, device='cpu', 
                        random_seed=1234, fixed_value=torch.empty(1).normal_()):
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)
        
    random_noise = torch.empty((n_samples, ld)).uniform_(-1, 1)#.normal_()

        
    with torch.no_grad():
        decoded = vae.decoder(random_noise)[0].detach()
        # classes = classifier(decoded).detach()
        # out = torch.nn.Softmax(dim=1)(classes)
        # out_argmax = torch.max(out, dim=1)
        

    return decoded#, out_argmax[1]

           
def sample_latent_codes(ld, n_samples, vae, classifier, device='cpu', 
                        random_seed=1234, fixed_value=torch.empty(1).normal_()):
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)
    latent_codes_dict = {}
    
    for dim in range(ld):
        # fixed_value = torch.empty(1).normal_()
        fixed_dim = fixed_value.expand((1, n_samples))
        
        random_noise = torch.empty((n_samples, ld)).uniform_(-3, 3) 
        random_noise[:, dim] = fixed_dim
        
        with torch.no_grad():
            decoded = vae.decoder(random_noise)[0].detach()
            classes = classifier(decoded).detach()
            out = torch.nn.Softmax(dim=1)(classes)
            out_argmax = torch.max(out, dim=1)
        
        latent_codes_dict[str(dim)] = out_argmax[1]
        
    return latent_codes_dict


def load_models(exp_vae, exp_classifier, load_c=False):
    vae_config = get_config(exp_vae)
    classifier_config = get_config(exp_classifier, key='model_opt')
    vae = init_vae(vae_config['vae_opt'], load_c=load_c)
    classifier = init_classifier(classifier_config['model_opt'])
    return vae, classifier


def generate_data_4_vae(n_samples, causal, constant_factor, pos_bins, classifier,
                        random_seed=1234):
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)
    
    dataset_zip = np.load('datasets/dsprites_ndarray_co1sh3sc6or40x32y32_64x64.npz')
    imgs = dataset_zip['imgs']
    
    # if causal:
    #     assert((pos_bins[5][-3] == 31 and constant_factor == [1, 0] and causal) or 
    #            (pos_bins[5][1] == 31 and constant_factor == [0, 1] and causal))
    # else:
    #     assert((pos_bins[5][-1] == 39 and pos_bins[5][-3] == 31 and not causal and 
    #             constant_factor == [1, 0, 0]) or 
    #            (pos_bins[5][-1] == 39 and pos_bins[5][1] == 31 and not causal and 
    #             constant_factor == [0, 1, 0]) or
    #            (pos_bins[5][1] == 31 and pos_bins[5][3] == 31 and not causal and 
    #             constant_factor == [0, 0, 1]))

    final_dict = {}
    for i in range(len(pos_bins)):
        d_sprite_idx, X_true_data, labels = caus_utils.calc_dsprite_idxs(
            num_samples=n_samples, seed=random_seed, constant_factor=constant_factor, 
            causal=causal, color=0, shape=2, scale=5, posXclass_min=pos_bins[i][0], 
            posXclass_max=pos_bins[i][1], posYclass_min=pos_bins[i][2], 
            posYclass_max=pos_bins[i][3], orient_min=pos_bins[i][4], 
            orient_max=pos_bins[i][5])
        D_data = caus_utils.make_dataset_d_sprite(
            d_sprite_dataset=imgs, dsprite_idx=d_sprite_idx, img_size=256)
        D_data_tensor_list = list(map(lambda t: torch.tensor(t).float().unsqueeze(0), 
                                      D_data))
        D_data_tensor = torch.cat(D_data_tensor_list).unsqueeze(1)
        classes = classifier(D_data_tensor)
        out = torch.nn.Softmax(dim=1)(classes)
        out_argmax = torch.max(out, dim=1)
        final_dict[str(i)] = out_argmax[1]
    return final_dict

def compute_mmd(sample1, sample2, alpha):
    """
    Computes MMD for samples of the same size bs x n_features using Gaussian
    kernel.
    
    See Equation (3) in http://www.jmlr.org/papers/volume13/gretton12a/gretton12a.pdf
    for the exact formula.
    """
    # Get number of samples (assuming m == n)
    m = sample1.shape[0]
    
    # Calculate pairwise products for each sample (each row). This yields
    # 2-norms |xi|^2 on the diagonal and <xi, xj> on non diagonal
    xx = torch.mm(sample1, sample1.t())
    yy = torch.mm(sample2, sample2.t())
    zz = torch.mm(sample1, sample2.t())
    
    # Expand the norms of samples into the original size
    rx = (xx.diag().unsqueeze(0).expand_as(xx))
    ry = (yy.diag().unsqueeze(0).expand_as(yy))
    
    # Remove the diagonal elements, the non diagonal are exactly |xi - xj|^2
    # = <xi, xi> + <xj, xj> - 2<xi, xj> = |xi|^2 + |xj|^2 - 2<xi, xj>
    kernel_samples1 = torch.exp(- alpha * (rx.t() + rx - 2*xx))
    kernel_samples2 = torch.exp(- alpha * (ry.t() + ry - 2*yy))
    kernel_samples12 = torch.exp(- alpha * (rx.t() + ry - 2*zz))
    
    # Normalisations
    n_same = (1./(m * (m-1)))
    n_mixed = (2./(m * m)) 
    
    term1 = n_same * torch.sum(kernel_samples1)
    term2 = n_same * torch.sum(kernel_samples2)
    term3 = n_mixed * torch.sum(kernel_samples12)
    return term1 + term2 - term3

def compute_mmd_dict(latent_dict, posX_gt_dict, posY_gt_dict, alpha):
    scores_dict = {}
    for latent_dim in latent_dict.keys():
        samples_latent = latent_dict[latent_dim].unsqueeze(1).float()
        # scores_dict[latent_dim] = {}
        scores = {}
        for Xgt_dim in posX_gt_dict.keys():
            samples_gt = posX_gt_dict[Xgt_dim].unsqueeze(1).float()
            mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
            scores['X' + Xgt_dim] = round(mmd_score.item(), 2)
    
        for Ygt_dim in posY_gt_dict.keys():
            samples_gt = posY_gt_dict[Ygt_dim].unsqueeze(1).float()
            mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
            scores['Y' + Ygt_dim] = round(mmd_score.item(), 2)
        scores_dict[latent_dim] = scores
    return scores_dict

def compute_argmin_mmd_archived(latent_dict, posX_gt_dict, posY_gt_dict, posT_gt_dict, 
                       result_dict, alpha):
    scores_dict = {}
    exact_dict = {}
    for latent_dim in latent_dict.keys():
        samples_latent = latent_dict[latent_dim].unsqueeze(1).float()
        X_min = []
        X_classes = []
        for Xgt_dim in posX_gt_dict.keys():
            samples_gt = posX_gt_dict[Xgt_dim].unsqueeze(1).float()
            mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
            X_min.append(round(mmd_score.item(), 3))
            X_classes.append(Xgt_dim)
        
        Y_min = []
        Y_classes = []
        for Ygt_dim in posY_gt_dict.keys():
            samples_gt = posY_gt_dict[Ygt_dim].unsqueeze(1).float()
            mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
            Y_min.append(round(mmd_score.item(), 3))
            Y_classes.append(Ygt_dim)
        
        if posT_gt_dict:
            T_min = []
            for Tgt_dim in posT_gt_dict.keys():
                samples_gt = posT_gt_dict[Tgt_dim].unsqueeze(1).float()
                mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
                T_min.append(round(mmd_score.item(), 3))
            results = [('X', min(X_min)), ('Y', min(Y_min)), ('T', min(T_min))]
        else: 
            results = [('X', min(X_min)), ('Y', min(Y_min))]
        factor = min(results, key = lambda t: t[1])
        scores_dict[latent_dim] = factor
        exact_dict[latent_dim] = factor[0] + X_classes[X_min.index(min(X_min))]
    return scores_dict, exact_dict


def compute_argmin_mmd(latent_dict, posX_gt_dict, posY_gt_dict, posT_gt_dict, 
                       result_dict, alpha):

    for latent_dim in latent_dict.keys():
        samples_latent = latent_dict[latent_dim].unsqueeze(1).float()
        X_min = []
        X_classes = []
        for Xgt_dim in posX_gt_dict.keys():
            samples_gt = posX_gt_dict[Xgt_dim].unsqueeze(1).float()
            mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
            X_min.append(round(mmd_score.item(), 3))
            X_classes.append(Xgt_dim)
        
        
        
        Y_min = []
        Y_classes = []
        for Ygt_dim in posY_gt_dict.keys():
            samples_gt = posY_gt_dict[Ygt_dim].unsqueeze(1).float()
            mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
            Y_min.append(round(mmd_score.item(), 3))
            Y_classes.append(Ygt_dim)
        
        # Log the minimum MMD score and the corresponding gt bin index 
        # (which corresponds to A class in the training data)
        results = [('X', min(X_min), X_classes[X_min.index(min(X_min))]),
                   ('Y', min(Y_min), Y_classes[Y_min.index(min(Y_min))])]
        
        # Add rotation if non causal
        if posT_gt_dict:
            T_min = []
            T_classes = []
            for Tgt_dim in posT_gt_dict.keys():
                samples_gt = posT_gt_dict[Tgt_dim].unsqueeze(1).float()
                mmd_score = compute_mmd(samples_latent, samples_gt, alpha)
                T_min.append(round(mmd_score.item(), 3))
                T_classes.append(Tgt_dim)
            results.append(('T', min(T_min), T_classes[T_min.index(min(T_min))]))
                
        # Get the minimum score of all factors and log it to the final result dict
        factor = min(results, key = lambda t: t[1])
        result_key = '{0}+{1}'.format(str(latent_dim), factor[0])
        result_dict[result_key][alpha]['MMD_score'].append(factor[1])
        result_dict[result_key][alpha]['unique_samples'].append(factor[0]+factor[2])
    return result_dict


def log_mmd_score(ld, causal, alpha_list, n_samples, var_range):
    """
    Computes MMD between the samples generated from a trained VAE where we 
    intervened on one dimension and ground truth samples where we kept one 
    factor fixed.

    Parameters
    ----------
    ld : TYPE
        DESCRIPTION.
    exp_file : TYPE
        DESCRIPTION.
    causal : TYPE
        DESCRIPTION.
    alpha_list : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    # Load the VAE and the classifier
    prefix = 'Non' if not causal else ''
    exp_vae = 'VAE_{0}CausalDsprite_ber_shape2_scale5_ld{1}'.format(prefix, str(ld))
    exp_classifier = prefix + 'CausalClassifier'
    vae, classifier = load_models(exp_vae, exp_classifier, load_c=True)
    print(' *- Loaded models:',  exp_vae, exp_classifier)
    
    # Generate the bin boundaries that correspond to each class.
    # Here step 4 equals the number of values in each bin when generatng data.
    posX_bins = [(0, 31, 0, 31, 0, 39)]#[(i, i+3, 0, 31, 0, 39) for i in range(0,31,4)]
    posY_bins = [(0, 31, 0, 31, 0, 39)] #[(0, 31, i, i+3, 0, 39) for i in range(0,31,4)]
    factor_list = ['X', 'Y']
    
    if causal:
        print(' *- Generating causal ground truth data...')

        # Limit one factor to one class and vary the rest of the variables 
        # in the SCM. Get the class labels of these images from the classifier.
        posX_gt_dict = generate_data_4_vae(100, True, [1,0], posX_bins, classifier)
        posY_gt_dict = generate_data_4_vae(100, True, [0,1], posY_bins, classifier)
        # Rotation is depended on the X and Y positions in this case.
        posT_gt_dict = None
        

    else:
        print(' *- Generating causal ground truth data...')
        
        # Generate the bin boundaries for the rotation variable which is in
        # this case independent. Here step 10 equals number of values in each 
        # bin when generatng data.
        factor_list.append('T')
        posT_bins = [(0, 31, 0, 31, i, i+10) for i in range(0,39,10)]    
        
        # Limit one factor to one class and vary the rest of the variables 
        # in the SCM. Get the class labels of these images from the classifier.
        posX_gt_dict = generate_data_4_vae(100, False, [1, 0, 0], posX_bins, classifier)
        posY_gt_dict = generate_data_4_vae(100, False, [0, 1, 0], posY_bins, classifier)
        posT_gt_dict = generate_data_4_vae(100, False, [0, 0, 1], posT_bins, classifier)
        
    
    ldim_factor_cartesian = itertools.product([str(dim) for dim in range(ld)],
                                         factor_list)
    ldim_factor_list = list(map(lambda t: t[0] + '+' + t[1], ldim_factor_cartesian))
    result_dict = {key: {alpha: {'MMD_score': [], 'unique_samples': []} \
                         for alpha in alpha_list} for key in ldim_factor_list}
        
    # Generate equidistant points on one dimension in the latent space. This 
    # corresponds to (n_samples) + 1 interventions.
    equidistant_points = (np.arange(n_samples + 1) / n_samples) \
        * 2 * var_range - var_range
    equal_noise = torch.from_numpy(equidistant_points).unsqueeze(1)
    
    # For each intervention, generate images, get their labels from the
    # classifier and compute the MMD between them and the labels obtained from
    # ground truth images generated above  with one fixed class
    for value in range(len(equal_noise)):
        
        # dictionary of labels for each dimension being interveened
        fixed_codes_dict = sample_latent_codes(
            ld, 100, vae, classifier, random_seed=2104, 
            fixed_value=equal_noise[value])
        
        # Compute MMD score for each alpha
        for alpha in alpha_list:      
            print(' *- Noise index {0}/{1}, alpha {2}'.format(value, len(equal_noise), alpha))
            result_dict = compute_argmin_mmd(
                fixed_codes_dict, posX_gt_dict, posY_gt_dict, posT_gt_dict, 
                result_dict, alpha=alpha)
            
    def get_res_key(latent_dim, d):
        factor_keys = list(map(lambda f: str(latent_dim)+'+'+f, factor_list))
        return [(f, d[f]) for f in factor_keys]

    # Order the result dictionary
    results = collections.OrderedDict(sorted(result_dict.items()))
    filename = 'corr_experiment/{0}C{1}r{2}s{3}U_{4}_mmds.csv'.format(
        prefix, ld, var_range, n_samples, exp_vae)
    header = ['latent_dim + gt_factor', 'unique_classes', 'ratio', 'alpha',
              'mmds_mean', 'std_mmds', 'latent_dim_range', 'count', 'n_samples']
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow([exp_vae])
        writer.writerow(header)
        # Compute the average MMD ratio across all alphas
        ratio_summary = {fac: [] for fac in results.keys()}
        for fac, alpha_dict in results.items():            
            for alpha, mmd_dict in alpha_dict.items(): 
                count = len(mmd_dict['unique_samples'])
                ratio = round(count/(n_samples +1), 3)
                assert(count == len(mmd_dict['MMD_score']))
                unique_classes = sorted(list(set(mmd_dict['unique_samples'])))
                mmd_mean = round(np.mean(mmd_dict['MMD_score']), 3)
                mmd_std = round(np.std(mmd_dict['MMD_score']), 3)
                ratio_summary[fac].append(ratio)
                writer.writerow([
                    fac, unique_classes, ratio, alpha, mmd_mean, 
                    mmd_std, var_range, count, n_samples])
            ratio_summary[fac] = round(np.mean(ratio_summary[fac]), 3)
        
        writer.writerow([])
        writer.writerow(['Per dimension per factor winner'])
        for k, v in ratio_summary.items():
            writer.writerow([k, v])
        
        writer.writerow([])
        writer.writerow(['Per dimension winner'])
        for dim in range(ld):
            writer.writerow(list(max(get_res_key(dim, ratio_summary), key=lambda x:x[1])))
        
                
    
alpha_list = [0.05, 0.1, 0.5, 1]
var_range = 3
n_samples = 49
causal = False
# for ld in [4]:
#     log_mmd_score(ld, causal, alpha_list, n_samples, var_range)




def plot_distributions(exp_vae, fixed_codes_dict, posX_gt_dict, posY_gt_dict):

    plt.figure(1, figsize=(30, 100))
    plt.clf()
    plt.suptitle(exp_vae)
    # Latent intevention
    for i in range(len(fixed_codes_dict.keys())):
        plt.subplot(len(fixed_codes_dict.keys()), len(posX_gt_dict.keys()) + 1, 
                    i*(len(posX_gt_dict.keys())+1) + 1)
        plt.hist(fixed_codes_dict[str(i)], bins=64)
        plt.title('vae fixed z' + str(i))
        plt.xlabel('class')
    
    for i in range(len(posX_gt_dict.keys())):
        plt.subplot(len(fixed_codes_dict.keys()), len(posX_gt_dict.keys()) + 1, i + 2)
        plt.hist(posX_gt_dict[str(i)], bins=64)
        plt.title('gt fixed z' + str(i))
        plt.xlabel('class')
    
    for i in range(len(posX_gt_dict.keys())):
        plt.subplot(len(fixed_codes_dict.keys()), len(posX_gt_dict.keys()) + 1, i + len(posX_gt_dict.keys()) + 3)
        plt.hist(posY_gt_dict[str(i)], bins=64)
        plt.title('gt fixed z' + str(i))
        plt.xlabel('class')
        
    plt.subplots_adjust(hspace=0.5)
    plt.show()
    
    
    
    for latent_dim in range(len(fixed_codes_dict)):
        plt.figure(latent_dim, figsize=(30, 100))
        plt.clf()
        plt.suptitle(exp_vae + ' with fixed latent {0} and fixed gt X'.format(str(latent_dim)))
        # Latent intevention
        n_distr = len(posX_gt_dict.keys())
        for i in range(n_distr):
            plt.subplot(2, n_distr/2, 1 + i)
            plt.hist(fixed_codes_dict[str(latent_dim)], bins=64, label='latent', alpha=0.5)
            plt.hist(posX_gt_dict[str(i)], bins=64, label='gt', alpha=0.5)
            plt.legend()
            plt.xlim(0, 64)
            plt.title('fixed gt class' + str(i))
            plt.xlabel('class')
        
        plt.subplots_adjust(hspace=0.5)
        plt.show()
        
        
    for latent_dim in range(len(fixed_codes_dict)):
        plt.figure(5 + latent_dim, figsize=(30, 100))
        plt.clf()
        plt.suptitle(exp_vae + ' with fixed latent {0} and fixed gt Y'.format(str(latent_dim)))
        # Latent intevention
        n_distr = len(posX_gt_dict.keys())
        for i in range(n_distr):
            plt.subplot(2, n_distr/2, 1 + i)
            plt.hist(fixed_codes_dict[str(latent_dim)], bins=64, label='latent', alpha=0.5)
            plt.hist(posY_gt_dict[str(i)], bins=64, label='gt', alpha=0.5)
            plt.legend()
            plt.xlim(0, 64)
            plt.title('fixed gt class' + str(i))
            plt.xlabel('class')
        
        plt.subplots_adjust(hspace=0.5)
        plt.show()

if False:
    ld = 10
    prefix = 'Non' if not causal else ''
    exp_vae = 'VAEConv2d_v2_{0}CausalDsprite_ber_shape2_scale5_ld{1}'.format(prefix, str(ld))
    exp_classifier = prefix + 'CausalClassifier'
    vae, classifier = load_models(exp_vae, exp_classifier, load_c=True)
    print(' *- Loaded models:',  exp_vae, exp_classifier)
    
    import pickle
    with open('datasets/test_causal_dsprite_shape2_scale5_imgs.pkl', 'rb') as f:
        test_data = pickle.load(f)
    
    i = 48
    dec = vae(test_data[i].unsqueeze(0))
    d = vae(test_data[i].unsqueeze(0))[0].detach().numpy().squeeze()
    plt.figure(1)
    plt.imshow(test_data[i].squeeze())
    plt.show()
    plt.figure(2)
    plt.imshow(d)
    plt.show()
    
    print(np.linalg.norm(dec[2].detach()))
    latent_normal = torch.distributions.Normal(dec[2], torch.exp(0.5*dec[3]))
    latent_samples = latent_normal.sample((20, 1)).squeeze()
    dec_latent = vae.decoder(latent_samples)    
    for i in range(3, 15):
        plt.figure(i)
        plt.imshow(dec_latent[0][i].squeeze().detach())
        plt.show()
    
    decoded = sample_prior(ld, 20, vae, classifier)
    for i in range(3, 15):
        plt.figure(i)
        plt.imshow(decoded[i].squeeze().detach())
        plt.show()