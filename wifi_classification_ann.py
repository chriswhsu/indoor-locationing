import os
import logging as lg
import numpy as np
# import matplotlib.pyplot as plt
import pandas as pd
import time
import glob
import math
import keras
# import h5py
from keras.models import Sequential
from keras.models import load_model
from keras.layers import Dense
from keras import metrics
# from keras import regularizers
# from keras.layers import Dropout
# from keras.constraints import maxnorm
from sklearn.model_selection import train_test_split

AP_COL_COUNT = 520

lg.basicConfig(level=lg.INFO,format='%(asctime)s %(levelname)s %(message)s')

##############
# Import data
##############

lg.info("Start loading data files.")
# training/validation set
train_val_set = pd.read_csv("UJIIndoorLoc_trainingData.csv")

# test set
test_set = pd.read_csv("UJIIndoorLoc_validationData.csv")
lg.info("Competed File Loading.")
##########################################
# Preprocess Data and Feature Engineering
##########################################

# ------------------------ training/validation set ----------------------------#

# Fingerprint data representation: positive-value representation for all WAPs.
# Original representation: -104 to 0 (weak to strong), 100 for no signal.
# New represenation: 1 to 105 (weak to strong), 0 for no signal.
min_train_db_val = train_val_set.iloc[:, 0:AP_COL_COUNT].min().min()  # minimum WAP is -104 dBm
train_val_set.iloc[:, 0:AP_COL_COUNT] = np.where(train_val_set.iloc[:, 0:AP_COL_COUNT] <= 0,
                                        train_val_set.iloc[:, 0:AP_COL_COUNT] + abs(min_train_db_val) + 1,
                                        train_val_set.iloc[:, 0:AP_COL_COUNT] - 100)

# Feature Scaling - do not center - destroys sparse structure of this data. 
# Normalize the WAPs by dividing by 105. Speeds up gradient descent.
max_pos_db_value = train_val_set.iloc[:, 0:AP_COL_COUNT].max().max()
train_val_set.iloc[:, 0:AP_COL_COUNT] = train_val_set.iloc[:, 0:AP_COL_COUNT] / max_pos_db_value

# Create a single label for the model to predict. FLOOR, LATITUDE, FLOOR, and
# BUILDINGID pinpoints the exact location of a user inside a building. Stack 
# train set and test set first before assigning unique location so that 
# identical locations are assigned the same UNIQUELOCATION value.
# use a category and it's codes rather than longer string for performance sake.

train_length = len(train_val_set)
lg.info("We have {0} records for training.".format(train_length))
combined = pd.concat([train_val_set, test_set])  # stack vertically
combined = combined.assign(UNIQUELOCATION=(combined['LONGITUDE'].astype(str) + '_' + combined['LATITUDE'].astype(str) + '_' + combined['FLOOR'].astype(str) + '_' + combined['BUILDINGID'].astype(str)).astype('category').cat.codes)
unique_locations = len(combined["UNIQUELOCATION"].unique())
lg.info("{0} unique locations".format(unique_locations))

# split again
train_val_set_coded = combined.iloc[0:train_length, :]
test_set_coded = combined.iloc[train_length:, :].copy()

lg.info("Split Data back into two sets.")

# Since UNIQUELOCATION is a multi-class label... 
dummy = keras.utils.to_categorical(train_val_set_coded['UNIQUELOCATION'], num_classes=unique_locations)
dummy = pd.DataFrame(dummy, dtype='int')
train_val_set_PUND = pd.concat([train_val_set_coded, dummy], axis=1)

X_train_val = train_val_set_PUND.iloc[:, 0:AP_COL_COUNT]
y_train_val = train_val_set_PUND.iloc[:, AP_COL_COUNT:2525]

lg.info("Finished setting up training set")

# -------------------------------- test set -----------------------------------#

# Fingerprint data representation
min_test_db_val = train_val_set_coded.iloc[:, 0:AP_COL_COUNT].min().min()
lg.info("Minimum test db Value: {0}".format(min_test_db_val))

lg.info("Scale Test Set")
test_set_coded.iloc[:, 0:AP_COL_COUNT] = np.where(test_set_coded.iloc[:, 0:AP_COL_COUNT] <= 0,
                                                  test_set_coded.iloc[:, 0:AP_COL_COUNT] + abs(min_test_db_val) + 1,
                                                  test_set_coded.iloc[:, 0:AP_COL_COUNT] - 100)

# Feature Scaling - do not center - destroys sparse structure of this data. 
# Normalize the WAPs by dividing by 105. Speeds up gradient descent.

max_test_db_val = test_set_coded.iloc[:, 0:AP_COL_COUNT].max().max()

# TODO
lg.info("Divide test set.")
test_set_coded.iloc[:, 0:AP_COL_COUNT] = test_set_coded.iloc[:, 0:AP_COL_COUNT] / max_test_db_val

# Since UNIQUELOCATION is a multi-class label...
dummy = keras.utils.to_categorical(test_set_coded['UNIQUELOCATION'], num_classes=unique_locations)
dummy = pd.DataFrame(dummy, dtype='int')
test_set_PUND = pd.concat([test_set_coded, dummy], axis=1)

X_test = test_set_PUND.iloc[:, 0:AP_COL_COUNT]
y_test = test_set_PUND.iloc[:, AP_COL_COUNT:2525]

# Split processed train_val set into training set and validation set

X_train, X_val, y_train, y_val = train_test_split(X_train_val, y_train_val,
                                                  test_size=0.2,
                                                  random_state=0)

# Create a reference table for looking up the LONGITUDE, LATITUDE, FLOOR, and
# BUILDINGID associated with each UNIQUELOCATION value.
ref_table = pd.concat([y_train.iloc[:, [0, 1, 2, 3, 9]],
                       y_val.iloc[:, [0, 1, 2, 3, 9]],
                       y_test.iloc[:, [0, 1, 2, 3, 9]]])
ref_table = ref_table.drop_duplicates()


# --- save data ---#
def save_data(dataframe, filename):
    file_present = glob.glob(filename)  # boolean, file already present?
    if not file_present:
        dataframe.to_csv(filename)
    else:
        print('WARNING: This file already exists.')


save_data(X_train, 'X_train_ann.csv')
save_data(y_train, 'y_train_ann.csv')
save_data(X_val, 'X_val_ann.csv')
save_data(y_val, 'y_val_ann.csv')
save_data(X_test, 'X_test_ann.csv')
save_data(y_test, 'y_test_ann.csv')

# --- load data ---#
X_train = pd.read_csv('X_train_ann.csv', index_col=0)
y_train = pd.read_csv('y_train_ann.csv', index_col=0)
X_val = pd.read_csv('X_val_ann.csv', index_col=0)
y_val = pd.read_csv('y_val_ann.csv', index_col=0)
X_test = pd.read_csv('X_test_ann.csv', index_col=0)
y_test = pd.read_csv('y_test_ann.csv', index_col=0)

# -- delete unneeded datasets created during preprocessing to free up memory --#
del train_val_set, train_val_set_coded
del test_set, test_set_coded, combined
del train_val_set_PUND, test_set_PUND, dummy, X_train_val, y_train_val

#################
# Train model(s)
#################

# ----------------------------- neural network --------------------------------#
# Explore various neural network hyperparameters and architectures to get best
# validation accuracy for predicting the UNIQUELOCATION. Will not use cross-
# validation in this project due to neural nets already being computationally
# expensive. Evaluate the model on the test set by calculating performances
# on each of multiple labels using a method defined.

# hyperparameters 
# for a list of hyperparameters tried, see "tuning_ann.csv"
hyperparameters = {'epochs': 100,  # SGD hyperparameter
                   'batch_size': 800,  # SGD hyperparameter
                   'hidden_layers': 1,
                   'neurons': 1600,  # neurons per hidden layer
                   'lambd': None,  # L2 regularization term
                   'dropout': None}  # dropout probability for dropout regularization


# default 1250, 1, 0, 0
def create_classifier(num_features, num_classes, hidden_layers=1,
                      neurons=1250, lambd=0, dropout=0):
    # create classifier
    classifier = Sequential()

    # L2 Reg ------------------------------------------------------#
    # add input and first hidden layer
    classifier.add(Dense(input_dim=num_features,
                         units=neurons,
                         kernel_initializer='glorot_uniform',
                         # kernel_regularizer=regularizers.l2(lambd),
                         activation='relu'))

    # add additional hidden layers(s) if specified
    for i in range(hidden_layers - 1):
        classifier.add(Dense(units=neurons,
                             kernel_initializer='glorot_uniform',
                             # kernel_regularizer=regularizers.l2(lambd),
                             activation='relu'))
    # -------------------------------------------------------------#

    # Dropout Reg  ------------------------------------------------#
    # In addition, each hidden layer's weights contrained to max norm not 
    # exceeding 3, as recommended in literature.

    # add input and first hidden layer
    # classifier.add(Dense(input_dim = num_features,
    #                     units = neurons, 
    #                     kernel_initializer = 'glorot_uniform',
    #                     kernel_constraint = maxnorm(3),
    #                     activation = 'relu'))

    # add additional hidden layers(s) if specified
    # for i in range(hidden_layers - 1):
    #    classifier.add(Dense(units = neurons, 
    #                 kernel_initializer = 'glorot_uniform',
    #                 kernel_constraint = maxnorm(3),
    #                 activation = 'relu'))
    #    classifier.add(Dropout(dropout))
    # -------------------------------------------------------------#

    # add output layer
    classifier.add(Dense(units=num_classes,
                         kernel_initializer='glorot_uniform',
                         activation='softmax'))

    # compile classifier 
    classifier.compile(loss='categorical_crossentropy',
                       optimizer='adam',
                       metrics=[metrics.categorical_accuracy])

    classifier.summary()
    return classifier


# fix seed for reproducibility and to minimize differences in model performance
# due to random processes. Due to some internal processes in Keras, won't be
# completely the same.
np.random.seed(0)

# training
classifier = create_classifier(num_features=X_train.shape[1],
                               num_classes=1995,
                               hidden_layers=hyperparameters['hidden_layers'],
                               neurons=hyperparameters['neurons'],
                               lambd=hyperparameters['lambd'],
                               dropout=hyperparameters['dropout'])
tic = time.time()
classifier.fit(X_train, y_train.iloc[:, 10:2005],
               batch_size=hyperparameters['batch_size'],
               epochs=hyperparameters['epochs'],
               verbose=True,
               shuffle=True)  # shuffle training data before each epoch
toc = time.time()
run_time = (toc - tic) / 60

# training set performance
train_results = classifier.evaluate(X_train, y_train.iloc[:, 10:2005])
classifier.metrics_names

# val set performance
val_results = classifier.evaluate(X_val, y_val.iloc[:, 10:2005], batch_size=5)
classifier.metrics_names

# write perforance results to tuning_ann.csv
results = pd.DataFrame({'model': 'ann', 'fit_time (min)': [run_time],
                        'epochs': [hyperparameters['epochs']],
                        'batch_size': [hyperparameters['batch_size']],
                        'hidden_layers': [hyperparameters['hidden_layers']],
                        'neurons_per_hidden_layer': [hyperparameters['neurons']],
                        'L2_reg_lambda': [hyperparameters['lambd']],
                        'dropout_reg_percent': [hyperparameters['dropout']],
                        'train_accuracy': [train_results[1]],
                        'val_accuracy': [val_results[1]],
                        'train_accuracy - val_accuracy': [train_results[1] - val_results[1]]})
with open('tuning_ann.csv', 'a') as f:
    results.to_csv(f, header=False, index=False)


# save best model 
def save_model(model, model_name):
    model_name_present = glob.glob(model_name)
    if model_name_present:
        os.remove(model_name_present[0])
    model.save(model_name)


save_model(classifier, 'ann_model.h5')

# load model
classifier = load_model('ann_model.h5')

# test set performance
y_pred = np.argmax(classifier.predict(X_test), axis=1)

y_test_pos = y_test.iloc[:, 0:2].values
y_test_floor = y_test.iloc[:, 2].values
y_test_building = y_test.iloc[:, 3].values

dict_loc = {}
m_total = ref_table.shape[0]
for i in range(m_total):
    key = int(ref_table.iloc[i]['UNIQUELOCATION'])
    value = ref_table.iloc[i, 0:4].values
    dict_loc[key] = value

y_pred_pos = np.asarray([dict_loc[i] for i in y_pred])[:, 0:2]
y_pred_floor = np.asarray([dict_loc[i] for i in y_pred])[:, 2]
y_pred_building = np.asarray([dict_loc[i] for i in y_pred])[:, 3]


def euclidean(y_test_pos, y_pred_pos):
    """
    Returns the prediction errors based on euclidean distances for each test 
    example. The prediction error for each test set example is the euclidean 
    distance between the test set's position (ground truth) and the predicted 
    position. A "position" is a pair of LONGITUDE and LATITUDE values, 
    e.g. -7515.92, 4.86489e+06.
    
    Arguments:
    y_test_pos -- test set positions represented by numpy array of shape 
                  (m_test, 2)
    y_pred_pos -- predicted test set position represented by numpy array of shape
                  (m_test, 2)
    
    Returns:
    D_error -- prediction errors between test set positions and predicted test 
               set positions represented by numpy array of shape (m_train, 1)
    """
    m_test = y_test_pos.shape[0]
    D_error = np.sum((y_test_pos - y_pred_pos) ** 2, axis=1) ** 0.5

    return D_error


D_error = euclidean(y_test_pos, y_pred_pos)  # position errors for each test set example, in order as they appear
sorted_D_error = sorted(D_error)

m_test = y_test.shape[0]
mean_error = np.mean(D_error)  # meters
percentile_25th = sorted_D_error[math.ceil(m_test * 0.25) - 1]  # -1 since 0-indexed. meters
percentile_50th = sorted_D_error[math.ceil(m_test * 0.50) - 1]  # meters
percentile_75th = sorted_D_error[math.ceil(m_test * 0.75) - 1]  # meters
percentile_95th = sorted_D_error[math.ceil(m_test * 0.95) - 1]  # meters
percentile_100th = sorted_D_error[math.ceil(m_test * 1.00) - 1]  # meters
building_hitrate = np.mean(y_test_building == y_pred_building)
floor_hitrate = np.mean(y_test_floor == y_pred_floor)
