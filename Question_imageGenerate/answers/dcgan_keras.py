import keras
import cv2
import numpy as np
import argparse
from glob import glob
import matplotlib.pyplot as plt

# GPU config
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf
from keras import backend as K
config = tf.ConfigProto()
config.gpu_options.allow_growth = True
config.gpu_options.visible_device_list="0"
sess = tf.Session(config=config)
K.set_session(sess)

# network
from keras.models import Sequential, Model
from keras.layers import Dense, Dropout, Activation, Flatten, Conv2D, MaxPooling2D, Input, BatchNormalization, Reshape, UpSampling2D, LeakyReLU, Conv2DTranspose

num_classes = 2
img_height, img_width = 32, 32 #572, 572
channel = 3

from keras.regularizers import l1_l2
from keras.initializers import RandomNormal as RN, Constant

def G_model(Height, Width, channel=3):
    inputs = Input((100,))
    in_h = int(Height / 16)
    in_w = int(Width / 16)
    d_dim = 64
    base = 64
    x = Dense(in_h * in_w * d_dim, name='g_dense1',
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(inputs)
    x = Reshape((in_h, in_w, d_dim), input_shape=(d_dim * in_h * in_w,))(x)
    x = Activation('relu')(x)
    x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='g_dense1_bn')(x)
    # 1/8
    #x = UpSampling2D(size=(2, 2))(x)
    x = Conv2DTranspose(base*4, (5, 5), name='g_conv1', padding='same', strides=(2,2),
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(x)
    #x = Conv2D(256, (5, 5), padding='same', name='g_conv1',
    #    kernel_initializer=RN(mean=0.0, stddev=0.02), bias_initializer=Constant())(x)
    x = Activation('relu')(x)
    x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='g_conv1_bn')(x)
    # 1/4
    #x = UpSampling2D(size=(2, 2))(x)
    x = Conv2DTranspose(base*2, (5, 5), name='g_conv2', padding='same', strides=(2,2),
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(x)
    #x = Conv2D(128, (5, 5), padding='same', name='g_conv2',
    #    kernel_initializer=RN(mean=0.0, stddev=0.02), bias_initializer=Constant())(x)
    x = Activation('relu')(x)
    x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='g_conv2_bn')(x)
    # 1/2
    #x = UpSampling2D(size=(2, 2))(x)
    x = Conv2DTranspose(base, (5, 5), name='g_conv3', padding='same', strides=(2,2),
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(x)
    #x = Conv2D(64, (5, 5), padding='same', name='g_conv3',
    #    kernel_initializer=RN(mean=0.0, stddev=0.02), bias_initializer=Constant())(x)
    x = Activation('relu')(x)
    x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='g_conv3_bn')(x)
    # 1/1
    #x = UpSampling2D(size=(2, 2))(x)
    x = Conv2DTranspose(channel, (5, 5), name='g_out', padding='same', strides=(2,2),
        kernel_initializer=RN(mean=0.0, stddev=0.02),  bias_initializer=Constant())(x)
    #x = Conv2D(channel, (5, 5), padding='same', activation='tanh', name='g_out',
    #    kernel_initializer=RN(mean=0.0, stddev=0.02), bias_initializer=Constant())(x)
    x = Activation('tanh')(x)
    model = Model(inputs=inputs, outputs=x, name='G')
    return model

def D_model(Height, Width, channel=3):
    base = 32
    inputs = Input((Height, Width, channel))
    x = Conv2D(base, (5, 5), padding='same', strides=(2,2), name='d_conv1',
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(inputs)
    x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='d_conv1_bn')(x)
    x = Conv2D(base*2, (5, 5), padding='same', strides=(2,2), name='d_conv2',
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(x)
    x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='d_conv2_bn')(x)
    x = Conv2D(base*4, (5, 5), padding='same', strides=(2,2), name='d_conv3',
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(x)
    x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='d_conv3_bn')(x)
    x = Conv2D(base*8, (5, 5), padding='same', strides=(2,2), name='d_conv4',
        kernel_initializer=RN(mean=0.0, stddev=0.02), use_bias=False)(x)
    x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization(momentum=0.9, epsilon=1e-5, name='d_conv4_bn')(x)
    x = Flatten()(x)
    #x = Dense(4096, activation='relu', name='d_dense1',
    #    kernel_initializer=RN(mean=0.0, stddev=0.02), bias_initializer=Constant())(x)
    x = Dense(1, activation='sigmoid', name='d_out',
        kernel_initializer=RN(mean=0.0, stddev=0.02), bias_initializer=Constant())(x)
    model = Model(inputs=inputs, outputs=x, name='D')
    return model

def Combined_model(g, d):
    model = Sequential()
    model.add(g)
    model.add(d)
    return model

    
CLS = {'background': [0,0,0],
       'akahara': [0,0,128],
       'madara': [0,128,0]}
    
# get train data
def data_load(path, hf=False, vf=False):
    xs = []
    paths = []
    
    for dir_path in glob(path + '/*'):
        for path in glob(dir_path + '/*'):
            x = cv2.imread(path)
            if channel == 1:
                x = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)
            x = cv2.resize(x, (img_width, img_height)).astype(np.float32)
            x /= 255.
            if channel == 1:
                x = np.expand_dims(x, axis=-1)
            else:
                x = x[..., ::-1]
            xs.append(x)
            
            paths.append(path)

            if hf:
                xs.append(x[:, ::-1])
                paths.append(path)

            if vf:
                xs.append(x[::-1])
                paths.append(path)

            if hf and vf:
                xs.append(x[::-1, ::-1])
                paths.append(path)

    xs = np.array(xs)

    return xs, paths


# train
def train():
    g = G_model(Height=img_height, Width=img_width, channel=channel)
    d = D_model(Height=img_height, Width=img_width, channel=channel)
    gan = Combined_model(g=g, d=d)

    g_opt = keras.optimizers.Adam(lr=0.02, beta_1=0.5)
    d_opt = keras.optimizers.Adam(lr=0.02, beta_1=0.5)
    #g_opt = keras.optimizers.SGD(lr=0.1, momentum=0.3, decay=1e-5)
    #d_opt = keras.optimizers.SGD(lr=0.1, momentum=0.1, decay=1e-5)

    g.compile(loss='binary_crossentropy', optimizer='SGD')
    d.trainable = False
    for layer in d.layers:
        layer.trainable = False
    gan.compile(loss='binary_crossentropy', optimizer=g_opt)

    d.trainable = True
    for layer in d.layers:
        layer.trainable = True
    d.compile(loss='binary_crossentropy', optimizer=d_opt)

    xs, paths = data_load('../Dataset/train/images/', hf=True, vf=True)

    # training
    mb = 4
    mbi = 0
    train_ind = np.arange(len(xs))
    np.random.seed(0)
    np.random.shuffle(train_ind)
    
    for i in range(1000):
        if mbi + mb > len(xs):
            mb_ind = train_ind[mbi:]
            np.random.shuffle(train_ind)
            mb_ind = np.hstack((mb_ind, train_ind[:(mb-(len(xs)-mbi))]))
            mbi = mb - (len(xs) - mbi)
        else:
            mb_ind = train_ind[mbi: mbi+mb]
            mbi += mb

        x = xs[mb_ind]

        input_noise = np.random.uniform(-1, 1, size=(mb, 100))
        g_output = g.predict(input_noise, verbose=0)
        X = np.concatenate((x, g_output))
        Y = [1] * mb + [0] * mb
        d_loss = d.train_on_batch(X, Y)
        # Generator training
        input_noise = np.random.uniform(-1, 1, size=(mb, 100))
        g_loss = gan.train_on_batch(input_noise, [1] * mb)

        print("iter >>", i+1, ",g_loss >>", g_loss, ',d_loss >>', d_loss)
    
    gan.save('model.h5')

# test
def test():
    # load trained model
    g = G_model(Height=img_height, Width=img_width, channel=channel)
    g.load_weights('model.h5', by_name=True)

    for i in range(3):
        input_noise = np.random.uniform(-1, 1, size=(9, 100))
        g_output = g.predict(input_noise, verbose=0)

        for i in range(9):
            gen = g_output[i]
            plt.subplot(3,3,i+1)
            plt.imshow(gen)

        plt.show()

    

def arg_parse():
    parser = argparse.ArgumentParser(description='CNN implemented with Keras')
    parser.add_argument('--train', dest='train', action='store_true')
    parser.add_argument('--test', dest='test', action='store_true')
    args = parser.parse_args()
    return args

# main
if __name__ == '__main__':
    args = arg_parse()

    if args.train:
        train()
    if args.test:
        test()

    if not (args.train or args.test):
        print("please select train or test flag")
        print("train: python main.py --train")
        print("test:  python main.py --test")
        print("both:  python main.py --train --test")
