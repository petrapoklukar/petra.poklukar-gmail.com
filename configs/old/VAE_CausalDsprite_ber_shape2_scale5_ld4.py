#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  4 11:41:40 2020

@author: petrapoklukar
"""

batch_size = 64

config = {}

# set the parameters related to the training and testing set
data_train_opt = {}
data_train_opt['batch_size'] = batch_size
data_train_opt['dataset_name'] = 'causal_dsprite_shape2_scale5_imgs'
data_train_opt['split'] = 'train'
data_train_opt['img_size'] = 256

data_test_opt = {}
data_test_opt['batch_size'] = batch_size
data_test_opt['dataset_name'] = 'causal_dsprite_shape2_scale5_imgs'
data_test_opt['split'] = 'test'
data_test_opt['img_size'] = 256

config['data_train_opt'] = data_train_opt
config['data_test_opt']  = data_test_opt

vae_opt = {
    'model': 'VAE_TinyResNet', # class name
    'filename': 'vae',
    'num_workers': 4,

    'loss_fn': 'fixed decoder variance', # 'learnable full gaussian',
    'learn_dec_logvar': False,
    'input_dim': 256*256*1,
    'input_channels': 1,
    'latent_dim': 4,
    'out_activation': 'sigmoid',
    'dropout': 0.3,
    'weight_init': 'normal_init',

    'conv1_out_channels': 32,
    'latent_conv1_out_channels': 128,
    'kernel_size': 3,
    'num_scale_blocks': 2,
    'block_per_scale': 1,
    'depth_per_block': 2,
    'fc_dim': 512,
    'image_size': 256,
    'decoder_param': 'bernoulli',

    'batch_size': batch_size,
    'snapshot': 3,
    'console_print': 1,
    'beta_warmup': 20,
    'beta_min': 0,
    'beta_max': 2,
    'beta_steps': 100,
    'kl_anneal': True,
    
    'epochs': 50,
    'lr_schedule': [(0, 1e-03), (10, 1e-04), (100, 1e-05)],
    'optim_type': 'Adam',
    'random_seed': 1201
}

config['vae_opt'] = vae_opt
config['algorithm_type'] = 'VAE_Algorithm'
