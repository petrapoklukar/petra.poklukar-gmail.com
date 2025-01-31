from __future__ import print_function
import argparse
import os
import sys
from importlib.machinery import SourceFileLoader
from algorithms import VAE_Algorithm_v2 as alg
import torch
from torch.autograd import Variable
import matplotlib.pyplot as plt
import numpy as np
import architectures.VAE_TinyResNet as vae
import cv2
import pickle
import random
import math
from scipy.stats import pearsonr
import datetime
import causal_utils as caus_utils
from lib.eval.hinton import hinton
from lib.eval.regression import *
from sklearn.linear_model import Lasso
from sklearn.ensemble.forest import RandomForestRegressor
from matplotlib.transforms import offset_copy
from lib.eval.regression import normalize
#from pygraphviz import *


import matplotlib
matplotlib.use('Qt5Agg')

#https://github.com/cianeastwood/qedr/blob/master/quantify.ipynb

# normalize input and target datasets [train, dev, test, (zeroshot)]
def normalize_datasets(datasets):
    datasets[0], mean, std, _ = normalize(datasets[0], remove_constant=False)
    datasets[1], _, _, _ = normalize(datasets[1], mean, std, remove_constant=False)
    datasets[2], _, _, _ = normalize(datasets[2], mean, std, remove_constant=False)
    if zshot:
        datasets[3], _, _, _ = normalize(datasets[3], mean, std, remove_constant=False)
    return datasets



def obtain_representation(test_set,config_file,checkpoint_file,dsprite=True):

    #load Vae
    vae_config_file = os.path.join('.', 'configs', config_file + '.py')
    vae_directory = os.path.join('.', 'models', checkpoint_file)
    vae_config = SourceFileLoader(config_file, vae_config_file).load_module().config 
    vae_config['exp_name'] = config_file
    vae_config['vae_opt']['exp_dir'] = vae_directory # the place where logs, models, and other stuff will be stored
    #print(' *- Loading config %s from file: %s' % (config_file, vae_config_file))   
    vae_algorithm = getattr(alg, vae_config['algorithm_type'])(vae_config['vae_opt'])
    #print(' *- Loaded {0}'.format(vae_config['algorithm_type']))
    vae_algorithm.load_checkpoint('models/'+config_file+"/"+checkpoint_file)
    vae_algorithm.model.eval()
    print("loaded vae")
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    #load the dataset
    #f= open(test_set, 'rb')
    input_data = test_set
    decoded_dim=[]
    for i in range(len(input_data)):

        img=input_data[i]
        img_in=img
        if dsprite:
            img=np.expand_dims(img,axis=-1)
        #toch the img and encode it
        x=torch.tensor(img).float().permute(2, 0, 1)
        x=x.unsqueeze(0)
        x = Variable(x).to(device)
        #dec_mean1, dec_logvar1, z, enc_logvar1=vae_algorithm.model.forward(x)
        dec_mean1, z, enc_logvar1=vae_algorithm.model.forward(x)
        
        decoded_dim.append(z[0].cpu().detach().numpy())
    decoded_dim=np.squeeze(np.array(decoded_dim))
    return decoded_dim


def fit_visualise_quantify(regressor, params, err_fn, importances_attr,z_encodes_train,z_encodes_test,gt_labels_train,gt_labels_test,model_names,  save_plot=False):
    # lists to store scores
    n_models=len(model_names)
    m_disent_scores   = [] * n_models
    m_complete_scores = [] * n_models
    
    # arrays to store errors (+1 for avg)
    n_g=gt_labels_train.shape[1]
    print("----")
    print(n_g)
    train_errs = np.zeros((n_models, n_g + 1))
    #dev_errs   = np.zeros((n_models, n_z + 1))
    test_errs  = np.zeros((n_models, n_g + 1)) 
    #zshot_errs = np.zeros((n_models, n_z + 1))
    
    # init plot (Hinton diag)
    fig, axs = plt.subplots(1,n_models, figsize=(12, 6), facecolor='w', edgecolor='k')
    axs = axs.ravel()

    
    
    for i in range(n_models):

        # init inputs
        #X_train, X_dev, X_test, X_zshot = m_codes[i][0], m_codes[i][1], m_codes[i][2], m_codes[i][3]
        X_test=z_encodes_test[i]
        X_train=z_encodes_train[i]
        
        


           
        # R_ij = relative importance of c_i in predicting z_j
        R = [] 

        latentens_train=np.array(z_encodes_train[i])
        #n#_c=latentens_train.shape[1]
        latentens_test=np.array(z_encodes_test[i])
        
        for j in range(n_g):
            print(j)
            # init targets [shape=(n_samples, 1)]
            #y_train = gts[0][:, j]
            #y_dev   = gts[1][:, j]
            #y_test  = gts[2][:, j] if test_time else None
            #y_zshot = gts[3][:, j] if zshot else None
            print(gt_labels_train.shape)
            y_train=gt_labels_train[:, j]
            y_test = gt_labels_test[:, j]
            # fit model
            model = regressor(**params[i][j])
            model.fit(X_train, y_train)
            # predict
            y_train_pred = model.predict(X_train)
            #y_dev_pred   = model.predict(X_dev)
            y_test_pred  = model.predict(X_test) #if test_time else None
            #y_zshot_pred = model.predict(X_zshot) if zshot else None
            
            # calculate errors
            train_errs[i, j] = err_fn(y_train_pred, y_train)
            #dev_errs[i, j]   = err_fn(y_dev_pred, y_dev)
            test_errs[i, j]  = err_fn(y_test_pred, y_test) #if test_time else None
            #zshot_errs[i, j] = err_fn(y_zshot_pred, y_zshot) if zshot else None            
            
            # extract relative importance of each code variable in predicting z_j
            r = getattr(model, importances_attr)[:, None] # [n_c, 1]
            R.append(np.abs(r))

        R = np.hstack(R) #columnwise, predictions of each z

        # disentanglement
        disent_scores = entropic_scores(R.T)
        c_rel_importance = np.sum(R,1) / np.sum(R) # relative importance of each code variable
        disent_w_avg = np.sum(np.array(disent_scores) * c_rel_importance)
        disent_scores.append(disent_w_avg)
        m_disent_scores.append(disent_scores)

        # completeness
        complete_scores = entropic_scores(R)
        complete_avg = np.mean(complete_scores)
        complete_scores.append(complete_avg)
        m_complete_scores.append(complete_scores)

        # informativeness (append averages)
        train_errs[i, -1] = np.mean(train_errs[i, :-1])
        #dev_errs[i, -1]   = np.mean(dev_errs[i, :-1])
        test_errs[i, -1]  = np.mean(test_errs[i, :-1]) #if test_time else None
        #zshot_errs[i, -1] = np.mean(zshot_errs[i, :-1]) if zshot else None

        # visualise
        hinton(R, '$\mathbf{g}$', '$\mathbf{z}$', ax=axs[i], fontsize=18)
        axs[i].set_title('{0}'.format(model_names[i]), fontsize=20)
    
    plt.rc('text', usetex=True)
    if save_plot:
        fig.tight_layout()
        plt.savefig("hint_{0}_{1}.png".format(regressor.__name__, n_g))
        print("saved")
    else:
        plt.show()

    print_table_pretty('Disentanglement', m_disent_scores, 'c', model_names)
    print_table_pretty('Completeness', m_complete_scores, 'z', model_names)

    print("Informativeness:")
    
    print_table_pretty('Training Error', train_errs, 'z', model_names)
    #print_table_pretty('Validation Error', dev_errs, 'z', model_names)
    
    #if test_time:
    print_table_pretty('Test Error', test_errs, 'z', model_names)
     #   if zshot:
     #       print_table_pretty('Zeroshot Error', zshot_errs, 'z', model_names)


# normalize input and target datasets [train, dev, test, (zeroshot)]
def normalize_datasets(datasets):
    datasets[0], mean, std, _ = normalize(datasets[0], remove_constant=False)
    datasets[1], _, _, _ = normalize(datasets[1], mean, std, remove_constant=False)
    datasets[2], _, _, _ = normalize(datasets[2], mean, std, remove_constant=False)
    if zshot:
        datasets[3], _, _, _ = normalize(datasets[3], mean, std, remove_constant=False)
    return datasets





def lasso(z_encodes_train,z_encodes_test,gt_labels_train,gt_labels_test,model_names):

    #Lasso
    n_z_max=10
    alpha = 0.02
    params = [[{"alpha": alpha}] * n_z_max] * len(model_names) # constant alpha for all models and targets
    importances_attr = 'coef_' # weights
    err_fn = nrmse # norm root mean sq. error
    save_plot = True
    fit_visualise_quantify(Lasso, params, err_fn, importances_attr, z_encodes_train,z_encodes_test,gt_labels_train,gt_labels_test,model_names, save_plot)



def random_forest(z_encodes_train,z_encodes_test,gt_labels_train,gt_labels_test,model_names):

    n_estimators = 10
    n_z_max=10
    #all_best_depths = [[12, 10, 10, 10, 10] , [12, 10, 3, 3, 3], [12, 10, 3, 3, 3], [4, 5, 2, 5, 5]]
    z_max_depths=[1,2,3,5,9]
    seed = 123
    rng = np.random.RandomState(seed)

    # populate params dict with best_depths per model per target (z gt)
    params = [[]] * len(model_names)
    for i in range(len(model_names)):
        for j in range(n_z_max):
            z_max_depth=z_max_depths[i]
            params[i].append({"n_estimators":n_estimators, "max_depth":z_max_depth, "random_state": rng})

    importances_attr = 'feature_importances_'
    err_fn = nrmse # norm root mean sq. error
    save_plot = True

    fit_visualise_quantify(RandomForestRegressor, params, err_fn, importances_attr, z_encodes_train,z_encodes_test,gt_labels_train,gt_labels_test,model_names, save_plot)





def main():

    causal = False

    if causal:      

        config_files=["VAEConv2D_v2_CausalDsprite_ber_shape2_scale5_ld2","VAEConv2D_v2_CausalDsprite_ber_shape2_scale5_ld3",
        "VAEConv2D_v2_CausalDsprite_ber_shape2_scale5_ld4","VAEConv2D_v2_CausalDsprite_ber_shape2_scale5_ld6","VAEConv2D_v2_CausalDsprite_ber_shape2_scale5_ld10"]
        model_names=["C-ld-2","C-ld-3","C-ld-4","C-ld-6","C-ld-10"]
        #checkpoint_files=["vae_checkpoint"+ str(i) + ".pth" for i in range(50)]  
        checkpoint_files=["vae_lastCheckpoint.pth"]


        dataset_zip = np.load('datasets/dsprites_ndarray_co1sh3sc6or40x32y32_64x64.npz')

        print('Keys in the dataset:', dataset_zip.keys())
        imgs = dataset_zip['imgs']

        #get the idxs
        data_sets=[]
        data_sets_true=[]
        d_sprite_idx,X_true_data,_=caus_utils.calc_dsprite_idxs(num_samples=10000,seed=12345,constant_factor=[0,0],causal=causal,color=0,shape=2,scale=5)
        X_true_data=np.array(X_true_data)[:,:2]
        #add a random g dimesnoion?
        #r_gen_data=[]
        #for r in range(len(X_true_data)):
        #	r_gen_data.append(random.uniform(0, 1))
        #X_true_data=np.array(X_true_data)
        #r_gen_data=np.array(r_gen_data)
        #print(X_true_data.shape)
        #print(r_gen_data.shape)
        #X_true_data=np.c_[ X_true_data, r_gen_data] 


        X_data=caus_utils.make_dataset_d_sprite(d_sprite_dataset=imgs,dsprite_idx=d_sprite_idx,img_size=256)
        print(len(X_data))
        X_data_t=X_data[8500:]
        X_data=X_data[:8500]        
        X_true_data_t=X_true_data[8500:]
        X_true_data=X_true_data[:8500]
        
    
    if not causal:
        # the custem girls dataset
        #config_files=["VAE_NonCausalDsprite_ber_shape2_scale5_ld2","VAE_NonCausalDsprite_ber_shape2_scale5_ld3","VAE_NonCausalDsprite_ber_shape2_scale5_ld4"
        #,"VAE_NonCausalDsprite_ber_shape2_scale5_ld6","VAE_NonCausalDsprite_ber_shape2_scale5_ld10"]
        #model_names=["NC_ds_ld2","NC_ds_ld3","NC_ds_ld4","NC_ds_ld6","NC_ds_ld10",]

        config_files=["VAEConv2D_v2_NonCausalDsprite_ber_shape2_scale5_ld2","VAEConv2D_v2_NonCausalDsprite_ber_shape2_scale5_ld3","VAEConv2D_v2_NonCausalDsprite_ber_shape2_scale5_ld4"
        ,"VAEConv2D_v2_NonCausalDsprite_ber_shape2_scale5_ld6","VAEConv2D_v2_NonCausalDsprite_ber_shape2_scale5_ld10"]
        model_names=["NC-ld-2","NC-ld-3","NC-ld-4","NC-ld-6","NC-ld-10"]

        

        #checkpoint_files=["vae_checkpoint"+ str(i) + ".pth" for i in range(50)]  
        checkpoint_files=["vae_lastCheckpoint.pth"]


        dataset_zip = np.load('datasets/dsprites_ndarray_co1sh3sc6or40x32y32_64x64.npz')

        print('Keys in the dataset:', dataset_zip.keys())
        imgs = dataset_zip['imgs']

        #get the idxs
        data_sets=[]
        data_sets_true=[]
        d_sprite_idx,X_true_data,_=caus_utils.calc_dsprite_idxs(num_samples=20000,seed=12345,constant_factor=[0,0,0],causal=causal,color=0,shape=2,scale=5)
        d_sprite_idx_t,X_true_data_t,_=caus_utils.calc_dsprite_idxs(num_samples=1500,seed=54321,constant_factor=[0,0,0],causal=causal,color=0,shape=2,scale=5)

        X_data=caus_utils.make_dataset_d_sprite(d_sprite_dataset=imgs,dsprite_idx=d_sprite_idx,img_size=256)
        X_data_t=caus_utils.make_dataset_d_sprite(d_sprite_dataset=imgs,dsprite_idx=d_sprite_idx_t,img_size=256)
    

    #split in train and test
    X_data_train=np.array(X_data)
    X_data_test=np.array(X_data_t)
    X_true_data_train,_,_,_=normalize(np.array(X_true_data),remove_constant=False)
    X_true_data_test,_,_,_=normalize(np.array(X_true_data_t),remove_constant=False)
    #swap to see

    #X_data_train[:,[0, 2]] = X_data_train[:,[2, 0]]
    #X_data_test[:,[0, 2]] = X_data_test[:,[2, 0]]
    #X_true_data_train[:,[0, 1]] = X_true_data_train[:,[1, 0]]
    #X_true_data_test[:,[0, 1]] = X_true_data_test[:,[1, 0]]



    zs_train_all=[]
    zs_test_all=[]
    for config_file in config_files:
        for checkpoint_file in checkpoint_files:
            print("obtaining representations (zs)")
            print(config_file)
            print(checkpoint_file)
            zs_train= obtain_representation(X_data_train,config_file,checkpoint_file)
            
            #plt.hist(zs_train, bins='auto')
            #plt.show()
            print(config_file)
            print("mean: " + str(np.mean(zs_train, axis=0)))
            print("std: " + str(np.std(zs_train, axis=0)))
            print("min: " + str(np.min(zs_train, axis=0)))
            print("max: " + str(np.max(zs_train, axis=0)))
            zs_test= obtain_representation(X_data_test,config_file,checkpoint_file)
            zs_train_n,_,_,_=normalize(zs_train,remove_constant=False)
            zs_test_n,_,_,_=normalize(zs_test,remove_constant=False)
            zs_train_all.append(zs_train_n)
            zs_test_all.append(zs_test_n)
    
    
    lasso(z_encodes_train=zs_train_all,z_encodes_test=zs_test_all,gt_labels_train=X_true_data_train,gt_labels_test=X_true_data_test,model_names=model_names)
    #random_forest(z_encodes_train=zs_train_all,z_encodes_test=zs_test_all,gt_labels_train=X_true_data_train,gt_labels_test=X_true_data_test,model_names=model_names)
    
    print("DONZO!")


   


if __name__== "__main__":
    main()






#fit_visualise_quantify(regressor, params, err_fn, importances_attr,z_encodes_train,z_encodes_test,gt_labels_train,gt_labels_test,  save_plot=False):


#random forrest
# n_estimators = 10
# all_best_depths = [[12, 10, 10, 10, 10] , [12, 10, 3, 3, 3], [12, 10, 3, 3, 3], [4, 5, 2, 5, 5]]

# # populate params dict with best_depths per model per target (z gt)
# params = [[]] * n_models
# for i, z_max_depths in enumerate(all_best_depths):
#     for z_max_depth in z_max_depths:
#         params[i].append({"n_estimators":n_estimators, "max_depth":z_max_depth, "random_state": rng})

# importances_attr = 'feature_importances_'
# err_fn = nrmse # norm root mean sq. error
# test_time = True
# save_plot = False

# fit_visualise_quantify(RandomForestRegressor, params, err_fn, importances_attr, test_time, save_plot)


# #plots
# zs = [0,0] + list(range(n_z))
# all_import_codes = [[5,8,4,0,2,1,1],[2,5,9,6,1,8,3],[5,7,2,6,1,9,3],[0,8,1,3,4,9,2]]
# n_samples = 5000
# fig, axs = plt.subplots(len(zs), n_models, figsize=(20, 25), facecolor='w', edgecolor='k', sharey=True, sharex=True)

# for i, import_codes in zip(range(n_models), all_import_codes):
#     X_train = m_codes[i][0]    
#     for j, (z, c) in enumerate(zip(zs, import_codes)):
#         X = X_train[:, c:c+1]
#         y = gts[0][:, z]
#         X, y = subset_of_data(X, y, n_samples)
        
#         if i == 0: # set column titles
#             axs[j,i].set_ylabel('$z_{0}$'.format(z), fontsize=28)
        
#         if j == 0:
#             axs[j,i].set_title('{0}'.format(model_names[i]), fontsize=28)

#         axs[j,i].set_xlabel('$c_{0}$'.format(c), fontsize=28)
#         axs[j,i].scatter(y, X, color='black', linewidth=0)        
#         axs[j,i].legend(loc=1, fontsize=21)
#         axs[j,i].set_ylim([-3.5,3.5])
#         axs[j,i].set_xlim([-2,2])
#         axs[j,i].grid(True)
#         axs[j,i].set_axisbelow(True)

# plt.rc('text', usetex=True)
# fig.tight_layout()
# #plt.show()
# plt.savefig(os.path.join(figs_dir, "cvsz.pdf"))


