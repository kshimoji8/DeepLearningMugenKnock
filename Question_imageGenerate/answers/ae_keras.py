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
from keras.layers import Dense, Dropout, Activation, Flatten, Conv2D, MaxPooling2D, Input, BatchNormalization, Reshape

num_classes = 2
img_height, img_width = 64, 64 #572, 572
out_height, out_width = 64, 64 #388, 388
channel = 3


def Mynet(train=False):
    inputs = Input((img_height, img_width, channel), name='in')
    h = Reshape([-1])(inputs)
    h = Dense(64)(h)
    #h = BatchNormalization()(h)
    out = Dense(out_height * out_width * channel, name='out')(h)
    
    model = Model(inputs=inputs, outputs=out, name='model')
    return model

    
CLS = {'background': [0,0,0],
       'akahara': [0,0,128],
       'madara': [0,128,0]}
    
# get train data
def data_load(path, hf=False, vf=False, rot=None):
    xs = []
    ts = []
    paths = []
    
    for dir_path in glob(path + '/*'):
        for path in glob(dir_path + '/*'):
            x = cv2.imread(path)
            if channel == 1:
                x = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)
            x = cv2.resize(x, (img_width, img_height)).astype(np.float32)
            x = x / 127.5 - 1
            if channel == 1:
                x = x[..., None]
            else:
                x = x[..., ::-1]
            xs.append(x)

            for i, cls in enumerate(CLS):
                if cls in path:
                    t = i
            
            ts.append(t)

            paths.append(path)

            if hf:
                xs.append(x[:, ::-1])
                ts.append(t)
                paths.append(path)

            if vf:
                xs.append(x[::-1])
                ts.append(t)
                paths.append(path)

            if hf and vf:
                xs.append(x[::-1, ::-1])
                ts.append(t)
                paths.append(path)

            if rot is not None:
                angle = 0
                scale = 1
                while angle < 360:
                    angle += rot
                    _h, _w, _c = x.shape
                    max_side = max(_h, _w)
                    tmp = np.zeros((max_side, max_side, _c))
                    tx = int((max_side - _w) / 2)
                    ty = int((max_side - _h) / 2)
                    tmp[ty: ty+_h, tx: tx+_w] = x.copy()
                    M = cv2.getRotationMatrix2D((max_side/2, max_side/2), angle, scale)
                    _x = cv2.warpAffine(tmp, M, (max_side, max_side))
                    _x = _x[tx:tx+_w, ty:ty+_h]
                    xs.append(x)
                    ts.append(t)
                    paths.append(path)
                    
    xs = np.array(xs, dtype=np.float32)
    ts = np.array(ts, dtype=np.int)
                    
    return xs, ts, paths

# train
def train():
    model = Mynet(train=True)

    for layer in model.layers:
        layer.trainable = True

    model.compile(
        loss={'out': 'mse'},
        optimizer=keras.optimizers.Adam(lr=0.001),#"adam", #keras.optimizers.SGD(lr=0.1, momentum=0.9, nesterov=False),
        loss_weights={'out': 1},
        metrics=['accuracy'])


    xs, ts, paths = data_load('../Dataset/train/images/', hf=True, vf=True, rot=1)

    # training
    mb = 256
    mbi = 0
    train_ind = np.arange(len(xs))
    np.random.seed(0)
    np.random.shuffle(train_ind)

    print(xs.shape)
    
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
        t = x.copy().reshape([mb, -1])

        loss, acc = model.train_on_batch(x={'in':x}, y={'out':t})
        print("iter >>", i+1, ",loss >>", loss, ',accuracy >>', acc)

    model.save('model.h5')

# test
def test():
    # load trained model
    model = Mynet(train=False)
    model.load_weights('model.h5')

    xs, ts, paths = data_load('../Dataset/test/images/')

    for i in range(len(paths)):
        x = xs[i]
        t = ts[i]
        path = paths[i]
        
        x = np.expand_dims(x, axis=0)
        
        pred = model.predict_on_batch(x={'in': x})[0]
        pred -= pred.min()
        pred /= pred.max()

        if channel == 1:
            pred = np.reshape(pred, (out_height, out_width))
        else:
            pred = np.reshape(pred, (out_height, out_width, channel))

        
            
        print("in {}".format(path))
   
        plt.subplot(1,2,1)
        if channel == 1:
            plt.imshow(x[0, ..., 0], cmap='gray')
        else:
            plt.imshow((x[0]+1)/2)
        plt.title("input")
        plt.subplot(1,2,2)
        plt.imshow(pred)
        plt.title("predicted")
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
