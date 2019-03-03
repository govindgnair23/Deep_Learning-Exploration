# -*- coding: utf-8 -*-
"""
Created on Wed Jan 30 19:26:02 2019

@author: learningmachine
"""
##################Import required packages#################
import numpy as np
from sklearn.preprocessing import OneHotEncoder
from torch import nn
import torch
from torch.utils.data import TensorDataset, DataLoader
import torch.nn.functional as F


#############################Read in and process input data#################
dino_names = open('dinos.txt','r').read()
dino_names = dino_names.lower().split('\n')
#Use a period as end of name token
dino_names = [dino_name+"." for dino_name in dino_names]
chars = list(set(''.join(dino_names)))
data_size, vocab_size = len(dino_names),len(chars)
print('There are %d total characters and %d unique characters in the data.'%(data_size,vocab_size))

####Longest dinosaur name####
longest_name   = max(dino_names,key=len)
longest_name_len = len(longest_name)




###Dictionaries mapping character to index and vice versa
char_to_idx = {ch:i for i,ch in enumerate(sorted(chars))}
ix_to_char =  {i:ch for i,ch in enumerate(sorted(chars))}
print(ix_to_char)

###Using padding to ensure each dino name has same length of 27###

dino_name_deficit = [27 - len(dino) for dino in dino_names]
dino_names = [dino_name + '.'*extra_len for dino_name,extra_len in zip(dino_names,dino_name_deficit)]

###Encoded version of dino names
encoded_dino_names = list(map(lambda x: [char_to_idx[char] for char in x], dino_names))
encoded_dino_array = np.array(encoded_dino_names)

####Create one hot encoder for each character in the dictionary###
one_hot_encoder = OneHotEncoder()
one_hot_encoder.fit(np.array(list(char_to_idx.values())).reshape(-1,1))
#one_hot_encoder.transform(np.array([1,2,3]).reshape(-1,1)).toarray()

##Target is obtained by shifting the inputs forward by 1 time step###
input_arr = encoded_dino_array
target_arr =  np.column_stack((input_arr[:,1:],np.zeros(input_arr.shape[0]))).astype(int)

#Create training and validation data
val_idx = int(len(input_arr)*(1-0.1))
train_X,train_y = input_arr[:val_idx],target_arr[:val_idx]
valid_X,valid_y = input_arr[val_idx:],target_arr[val_idx:]




print("\t\t Feature Shapes:")
print("Train_set:\t\t{}".format(train_X.shape))
print("\nValidation Set: \t{}".format(valid_X.shape))

###DataLoaders and Batching
train_data = TensorDataset(torch.from_numpy(train_X),torch.from_numpy(train_y))
valid_data = TensorDataset(torch.from_numpy(valid_X),torch.from_numpy(valid_y))

batch_size = 2

train_loader = DataLoader(train_data,batch_size=batch_size)
valid_loader = DataLoader(valid_data,batch_size=batch_size)


# check if GPU is available
train_on_gpu = torch.cuda.is_available()

###################Function to geenrate batches of inputs and targets#######################
##########Function borrowed from Udacity - Intro to Pytorch course##########################

def get_batches(input_arr,target_arr, batch_size = 1 ):
    
    '''Create a generator that returns batches of size
       batch_size x 27(seq_length) from arr.
       
       Arguments
       ---------
       input_arr & target_arr: Array you want to make batches from
       batch_size: Batch size, the number of dinosaur names in each batch
       seq_length: Number of encoded chars in a sequence(fixed at 27)
    '''


    n_batches  = int(input_arr.shape[0]/batch_size)    
    
    for i in range(n_batches):
        x = input_arr[i*batch_size:(i+1)*batch_size,:]
        y = target_arr[i*batch_size:(i+1)*batch_size,:]
        yield x,y
        
    
    
####Define Neural  Net##########
        
class CharRNN(nn.Module):
    
    
    def __init__(self,tokens,n_hidden=128,n_layers=2,drop_prob=0.25,lr=0.001):
         super().__init__()
         self.drop_prob = drop_prob
         self.n_layers = n_layers
         self.n_hidden = n_hidden
         self.lr =lr
         
         #creating character dictionaries
         self.chars = tokens
         self.int2char = {i:ch for i,ch in enumerate(sorted(chars))}
         self.char2int = {ch:i for i,ch in enumerate(sorted(chars))}
         
         ##Define LSTM
         self.lstm = nn.LSTM(len(self.chars),n_hidden,n_layers,dropout = drop_prob,batch_first = True)
         #Define a drop out layer
         self.dropout = nn.Dropout(drop_prob)
         ##Fully connected layer
         self.fc = nn.Linear(n_hidden,len(self.chars))
         
        
    def forward(self,x,hidden):
        
        ''' Forward pass through the network.
            The inputs are x and the hidden cell/state  is hidden'''
        
        #Pass input and incoming hidden through lstm
        lstm_out, hidden = self.lstm(x,hidden)
        
        #Pass through dropout layer
        out = self.dropout(lstm_out)
        
        # Stack up LSTM outputs using view
        out = lstm_out.contiguous().view(-1, self.n_hidden)
        
        
      
        ###Pass through fully connected layer
        out = self.fc(out)
        
        return(out,hidden)
        
        
    
    def init_hidden(self,batch_size):
        '''Initalize hidden state'''
        
        weight = next(self.parameters()).data
        
        if(train_on_gpu):
            hidden = (weight.new(self.n_layers,batch_size,self.n_hidden).zero_().cuda(),
                       weight.new(self.n_layers,batch_size,self.n_hidden).zero_().cuda())
        else:
            hidden = (weight.new(self.n_layers, batch_size, self.n_hidden).zero_(),
                      weight.new(self.n_layers, batch_size, self.n_hidden).zero_())
        
        return(hidden) 
    
    
 ###Below function borrowed from Udacity course   
def train(net,epochs=10,batch_size =1, seq_length =27,lr =0.001,clip =5,print_every =10):
    
    '''
         net : CharRNN Network
         input_data: text data to train network
         target_data: text data to predict
         epochs: No of epochs to train
         batch_size : No of dinosaur names to train at a time
         seq_length: No of character steps per batch(27)/dinosaur name
         lr : Learning rate
         clip: gradient clipping
         print_every: No of steps for printing and training and validation loss
    '''
    
    
    opt = torch.optim.Adam(net.parameters(),lr=lr)
    criterion = nn.CrossEntropyLoss()
    

    
    if(train_on_gpu):
        net.cuda()
    
    net.train() # Set to training mode
    
    counter = 0
    
    for e in range(epochs):
        #initialize hidden state
        h = net.init_hidden(batch_size)
        
        for inputs,targets in train_loader:
            inputs = inputs.numpy()
            inputs = one_hot_encoder.transform(inputs.reshape(-1,1)).toarray().reshape(batch_size,seq_length,-1)
            #COnvert inputs back to Tesnor
            inputs = torch.Tensor(inputs)
            
            counter+=1
            
            
                
            if (train_on_gpu):
                inputs, targets = inputs.cuda(),targets.cuda().long()
                
            ##Create new variables for hidden state as we don't
            ##want to backprop between batches
            h = tuple([each.data for each in h])
            
            #zero accumulated gradients
            net.zero_grad()
            
            #Get output from model
            
            output,h = net(inputs,h)
            output = output.reshape(batch_size,seq_length,-1)
            
            #Calculate loss and perform backprop
            loss = criterion(output,targets)
            loss.backward()
            
            #Perform gradient clipping to prevent gradient explosion
            nn.utils.clip_grad_norm(net.parameters(),clip)
            
            opt.step()
            
            ##Get loss stats from validation data
            
            if counter%print_every==0:
                val_h = net.init_hidden(batch_size)
                val_losses =[]
                net.eval() # Set to evaluation mode
                ##Get validation data
                for inputs,targets in valid_loader:
                    inputs = inputs.numpy()
                    inputs = one_hot_encoder.transform(inputs.reshape(-1,1)).toarray().reshape(batch_size,seq_length,-1)
                    #Convert inputs back to Tesnor
                    inputs = torch.Tensor(inputs)
                    
                
            
                    ##Create new hidden state for each batch
                    val_h = tuple([each.data for each in val_h])
                    
                    if train_on_gpu:
                        inputs,targets = inputs.cuda(), targets.cuda().long()
                        
                    output,val_h = net(inputs,val_h)
                    output = output.reshape(batch_size,seq_length,-1)
                    val_loss = criterion(output,targets)
                    
                    val_losses.append(val_loss)
                    
                
                net.train()
                
                print("Epoch: {}/{}...".format(e+1, epochs),
                      "Step: {}...".format(counter),
                      "Loss: {:.4f}...".format(loss.item()),
                      "Val Loss: {:.4f}".format(np.mean([x.item() for x in val_losses])))
                    
                    
 ####Instantiating the model##########
n_hidden= 256
n_layers =2
 
net = CharRNN(chars,n_hidden,n_layers) 


###############Train the model###################

n_epochs = 20
train(net,epochs= n_epochs,batch_size =batch_size, seq_length =27,lr =0.001,clip =5,print_every =10)

 
############Save model for later use###########
model_name = 'char_rnn_20epoch.net'

checkpoint = {'n_hidden':net.n_hidden,
              'n_layers': net.n_layers,
              'state_dict':net.state_dict(),
              'tokens': net.chars}

with open(model_name,'wb') as f:
    torch.save(checkpoint,f)
    
##################################################3
###Function to predict next character given an input character###
## Returns the predicted charcater and hidden state##############
    
def predict(net,char,h=None,top_k =None):
    
    #Get inputs in one hot encoded tensor form
    x = np.array([[net.char2int[char]]])
    x = one_hot_encoder.transform(x).toarray()
    inputs = torch.from_numpy(x).unsqueeze(1).to(dtype = torch.float32)
    
    if(train_on_gpu): 
        inputs = inputs.cuda()
        
    #detach hidden state from history
    h = tuple(each.data for each in h)
    #Get output of the model
    out,h = net(inputs,h)

    #Get charcater probabilties
    p = F.softmax(out,dim=1).data
    if(train_on_gpu): 
        p = p.cpu() # move to cpu
        
    #get top characters
    if top_k is None:
        top_ch = np.arange(len(net.chars))
    else: 
        p, top_ch = p.topk(top_k)
        top_ch = top_ch.numpy().squeeze()
        
    # select next likely character
    p = p.numpy().squeeze()
    char = np.random.choice(top_ch,p = p/p.sum())
    
    #return enocded value of next character and hidden state
    return(net.int2char[char],h)
    

###Priming and generating text###
def sample(net,max_length =27,prime ='t', top_k =None): 
    if(train_on_gpu):
        net.cuda()
    else:
        net.cpu()
        
    net.eval() #eval mode
    
    ##Run through priming characters
    chars = [ch for ch in prime]
    h = net.init_hidden(1)
    for ch in prime:
        char,h = predict(net,ch,h,top_k = top_k)
        
    chars.append(char)
    
    ii = len(prime) # Length of dinosaur name
    ##Now pass in previous charcaters to get new one
    while(char != "." and ii <= max_length):
        char,ch = predict(net,chars[-1],h, top_k = top_k)
        chars.append(char)
        ii +=1
    
    return ''.join(chars)

print(sample(net,prime ='m',top_k =3))
    
    
    
        
    
        
        
    
    
    
    
    
    
         
         
        
        
            
    
 
    
    
    
    












