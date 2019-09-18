from phe import paillier
from twocloud_client import PlaintextCloud
import math
import random
import copy
class SpecSubED():
    def __init__(self,decrypt_cloud: PlaintextCloud, 
                inc = 160,
                window_len=400, 
                a_in = 4,
                b_in = 0.001,
                NIS = 23,
                quantizer=2**32):

        self.inc = inc
        self.wlen = window_len #windowlen
        self.Len_message = None
        self.Num_w = None

        self.Q=quantizer
        self.A = int(a_in * quantizer)
        self.B = int(b_in * quantizer)
        self.NIS = NIS
        self.alpha_hamming = 0.46

        self.cloud=decrypt_cloud
        self.pvk = self.cloud.get_privatekey()
        self.pbk = self.cloud.pbk

        self.mul_qua=self.cloud.multiply_with_quantizer
        self.mul = self.cloud.multiply
        self.div = self.cloud.divide
        self.sqrt = self.cloud.square_root
        self.big = self.cloud.bigger


    def spec_sub(self, signal_in):


        self.Len_message = len(signal_in)
        self.Num_w=(self.Len_message - self.wlen) // self.inc + 1

        self.print_info()
        sptrRe, sptrIm = self.enframed_windowed_dft(signal_in) # Q^3

        sptrRe, sptrIm = self.sptr_sub(sptrRe,sptrIm) # NIS^0.5 * Q^15
        outSignal = self.overlap_add(sptrRe,sptrIm)
        return outSignal

    def enframed_windowed_dft(self, signal_in):

        sptrRe = [[]] * self.Num_w           # wlen * Num_w  
        sptrIm = [[0]*self.wlen] * self.Num_w
        window = self.get_hamming_window(self.wlen)     #  Q int


        for index_w in range(self.Num_w):
            temp = [0] * self.wlen
            for j in range(self.wlen):
                temp[j] = signal_in[index_w *self.inc + j] * window[j] # Q^2

            re, im = self.DFT(temp) # Q^3 
            sptrRe[index_w] = re
            sptrIm[index_w] = im
            print('Process 1 enframed windowed: {}|{}'.format(index_w,self.Num_w -1))

        return sptrRe, sptrIm # Q^3



    def sptr_sub(self, sptrRe, sptrIm):
        amp_avg = [0] * self.wlen   # Q^6
        amp = []

        for i in range(self.Num_w):
            amp_row = []
            for j in range(self.wlen):
                x = self.mul(sptrRe[i][j], sptrRe[i][j]) # Q^6
                y = self.mul(sptrIm[i][j], sptrIm[i][j]) # Q^6
                amp_row.append(x + y)
            amp.append(amp_row)
            print('Process 21 amplitude: {}|{}'.format(i,self.Num_w -1))

        for i in range(self.wlen):
            for j in range(self.NIS):
                amp_avg[i] = amp_avg[i] + amp[j][i] #  NIS * Q^6
            print('Process 22 avg amplitude: {}|{}'.format(i,self.wlen -1))

        for i in range(self.wlen):
            A_amp = self.A * amp_avg[i] # int * EncryptedNumber # NIS * Q^7
            B_amp = self.B * amp_avg[i] # NIS * Q^7

            for j in range(self.Num_w):
                
                x = self.NIS * self.Q * amp[j][i] - A_amp # NIS * Q * Q^6 - NIS * Q^7 = NIS * Q^7
                x = self.big(x, B_amp)

                x = self.div(x, amp[j][i], self.Q ** 7) # (NIS * Q^7) / Q^6 * Q^7 = NIS * Q^8
                # print('x div = ', self.pvk.decrypt(x)/(self.NIS * self.Q ** 8))
                x = self.sqrt(x, self.Q ** 5) #  NIS^0.5 * Q^9
                # print('x sqrt = ', self.pvk.decrypt(x)/(self.NIS ** 0.5 * self.Q ** 9))

                sptrRe[j][i] = self.mul(sptrRe[j][i], x) # Q^6 * NIS^0.5 * Q^9 = NIS^0.5 * Q^15
                # print('x mul 15 = ', self.pvk.decrypt(sptrRe[j][i])/(self.NIS **0.5 * self.Q ** 15))
                # input()
                sptrIm[j][i] = self.mul(sptrIm[j][i], x) # NIS^0.5 * Q^15
            print('Process 23 remove nosie: {}|{}'.format(i,self.wlen -1))
        return sptrRe, sptrIm

        

    def overlap_add(self, sptrRe, sptrIm): # NIS^0.5 * Q^15
        outSignal = [0] * self.Len_message 

        for i in range(self.Num_w):
            re, _ = self.DFT(sptrRe[i], sptrIm[i])
            for j in range(self.inc):
                outSignal[i * self.inc + j] = outSignal[i * self.inc + j] + re[j]
            print('Process 3 overlap add: {}|{}'.format(i,self.Num_w -1))

        return outSignal
        

    def DFT(self, re_in, img_in = None):  # Q^2
        len_s = len(re_in)
        p = (-2 * math.pi) / len_s

        aux_re, aux_im = [], [] # Q int

        for i in range(len_s):
            row_re, row_im = [], []
            for j in range(len_s):
                x = int(math.cos(i * j * p) * self.Q)
                y = int(math.sin(i * j * p) * self.Q)
                row_re.append(x)
                row_im.append(y)
            aux_re.append(row_re)
            aux_im.append(row_im) # Q

        re, im = [0] * len_s, [0] * len_s
        for i in range(len_s):
            for j in range(len_s):
                x = re_in[j] * aux_re[i][j] # Q^3
                re[i] = re[i] + x
                y = re_in[j] * aux_im[i][j] 
                im[i] = im[i] + y
                break
        if img_in:
            for i in range(len_s):
                for j in range(len_s):
                    x = -1 * aux_re[i][j] * img_in[j] # QQ
                    re[i] = re[i] + x
                    y = -1 * aux_im[i][j] * img_in[j] # QQ
                    im[i] = im[i] + y
                    break
        return re, im # Q^3


    def get_hamming_window(self, wlen):
        win = []
        p = (2 * math.pi) / (self.wlen - 1)
        for i in range(wlen):
            x = math.cos(p * i)
            x = self.alpha_hamming * x + (1 - self.alpha_hamming)
            x = int(x * self.Q)
            win.append(x)
        return win # 1 * wlen int Q
        
    def print_info(self):
        print()
        print('-'*40)
        print('Encrypted info:')
        print('Q: ',self.Q)
        print()

        print('siginal info:')
        print('Len_message:',self.Len_message)
        print('inc: ',self.inc)
        print('wlen: ',self.wlen)
        print('Num_w: ',self.Num_w)
        print()

        print('spec sub infor')
        print('A: ',self.A)
        print('B: ',self.B)
        print('NIS: ',self.NIS)
        print('alpha_hamming: ',self.alpha_hamming)
        print('-'*40)
        print()
        




if __name__=='__main__':
    q=2**32
    ft=SpecSubED(PlaintextCloud(('127.0.0.1',9999)),
                inc = 50    ,
                window_len=64, 
                a_in = 4,
                b_in = 0.001,
                NIS = 2,
                quantizer=2**32) #
    pbk=ft.cloud.pbk
    pvk=ft.cloud.get_privatekey()

    sigin=[]

    f = open('./data/lms_input.txt', 'r')
    for index, l in enumerate(f):
        sigin.append(pbk.encrypt(int(float(l)*q)))
        print('Reading: {}|{}'.format(index,256))
    f.close()
    #sigin # Q
    out=ft.spec_sub(sigin)
    print("Done!")

    # noise,sigin=[],[]
    # f = open('c:/users/hjm/desktop/noise.txt', 'r')
    # for l in f:
    #     noise.append(pbk.encrypt(int(float(l)*q)))
    # f.close()
    # f = open('c:/users/hjm/desktop/lms_input.txt', 'r')
    # for l in f:
    #     sigin.append(pbk.encrypt(int(float(l)*q)))
    # f.close()
    # out,err=ft.lms(noise,sigin)

    # f=open('c:/users/hjm/desktop/lms_output.txt','w')
    # for e in err:
    #     f.write(str(pvk.decrypt(e)/q)+'\n')
    # f.close()
