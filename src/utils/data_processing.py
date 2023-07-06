import scipy.io
import torch
import os
from utils.config_module import config

def makePathAndDirectories(training=True):
	## make paths and directories for training
	if training == True:
		return	makePathAndDirectoriesTraining()
	elif training == False:
		return	makePathAndDirectoriesTesting()
  
def makePathAndDirectoriesTraining():
	path_save_model   = os.path.join(config["path"]["saveModel"],config["experiment"]["model"],config["experiment"]["generator"],config["experiment"]["name"],"")
	path_training_log = os.path.join(config["path"]["saveModel"], "training_log",config["experiment"]["model"],config["experiment"]["generator"],config["experiment"]["name"],"")
	path_loss_plot    = os.path.join(path_training_log, "loss_plot","")
	os.makedirs(path_training_log,exist_ok=True)
	os.makedirs(path_loss_plot,exist_ok=True)
	os.makedirs(path_save_model,exist_ok=True)
	
	return path_save_model, path_training_log, path_loss_plot

def makePathAndDirectoriesTesting():
	path_save_model   = os.path.join(config["path"]["saveModel"],config["experiment"]["model"],config["experiment"]["generator"],config["experiment"]["name"],"")
	path_inference	  = os.path.join(config["path"]["inference"],config["experiment"]["model"],config["experiment"]["generator"],config["experiment"]["name"],"")
	
	return path_save_model, path_inference

def importDataset(only_test=False):
	"""
		returns dictionary of features-labels for train, val, test datasets
		return shape: (batch,channel,height,width)
	"""
	path = config["path"]["trainingData"]
	train_val_test_split = config["training"]["trainValTestSplit"]
	num_heads = config["experiment"]["outputHeads"]

	ntrain = train_val_test_split[0]
	nval = train_val_test_split[1]
	ntest = train_val_test_split[2]

	if num_heads==1:
		pre_filepath = "mat_files/PK11"
	elif num_heads==5:
		pre_filepath = "mat_files/PK15689"
	else: 
		raise AssertionError("Unexpected num_heads.")

	if only_test:
		test = scipy.io.loadmat(os.path.join(path,f"{pre_filepath}_test.mat"))
		test["input"] = torch.tensor(test["input"][:ntest]).permute(0,3,1,2).float()	
		if len(test["output"].shape) == 3:
			test["output"] = torch.tensor(test["output"][:ntest])[:,None,:,:].float()
		elif len(test["output"].shape) == 4:
			test["output"] = torch.tensor(test["output"][:ntest]).permute(0,3,1,2).float()
		else: 
			raise AssertionError("Unexpected shape for y.")
		return [],[], test
	
	else:
		train = scipy.io.loadmat(os.path.join(path,f"{pre_filepath}_train.mat"))
		val = scipy.io.loadmat(os.path.join(path,f"{pre_filepath}_val.mat"))
		test = scipy.io.loadmat(os.path.join(path,f"mat_files/test_100/PK15689_test.mat"))

		train["input"] = torch.tensor(train["input"][:ntrain]).permute(0,3,1,2).float()
		val["input"] = torch.tensor(val["input"][:nval]).permute(0,3,1,2).float()
		test["input"] = torch.tensor(test["input"][:ntest]).permute(0,3,1,2).float()	

		if len(train["output"].shape) == 3:
			train["output"] = torch.tensor(train["output"][:ntrain])[:,None,:,:].float()
			val["output"] = torch.tensor(val["output"][:nval])[:,None,:,:].float()
			test["output"] = torch.tensor(test["output"][:ntest])[:,None,:,:].float()
		elif len(train["output"].shape) == 4:
			train["output"] = torch.tensor(train["output"][:ntrain]).permute(0,3,1,2).float()
			val["output"] = torch.tensor(val["output"][:nval]).permute(0,3,1,2).float()
			test["output"] = torch.tensor(test["output"][:ntest]).permute(0,3,1,2).float()
		else: 
			raise AssertionError("Unexpected shape for y.")
		return train, val, test

def scaleDataset(train_data, val_data):
		## define normalizers based on training data
		scalerName = config["dataProcessing"]["scaler"]
		if scalerName == "MinMax":
			x_normalizer = MinMaxScaling(train_data["input"])
			y_normalizer = MinMaxScaling(train_data["output"])
		elif scalerName == "Gaussian":
			x_normalizer = GaussianScaling(train_data["input"])
			y_normalizer = GaussianScaling(train_data["output"])
		else:
			raise AssertionError("Unexpected argument for scalerName.")

		x_train	= x_normalizer.encode(train_data["input"])
		y_train	= y_normalizer.encode(train_data["output"])
		x_val	= x_normalizer.encode(val_data["input"])
		y_val	= y_normalizer.encode(val_data["output"])

		return x_train, y_train, x_val, y_val, x_normalizer, y_normalizer


class GaussianScaling():
	def __init__(self, x, eps=0.00001):
		# works for shape (batchsize, channels, dim1, dim2)
		# computes mean, std of shape (channels)
		# 1 set of parameters for each channel
		self.mean = torch.mean(x, (0,2,3))      
		self.std = torch.std(x, (0,2,3))
		self.eps = eps

	def encode(self, x):
		z = torch.ones_like(x)
		for i in range(len(self.mean)):
			z[:,i,:,:] = (x[:,i,:,:] - self.mean[i]) / (self.std[i] + self.eps)
		return z

	def decode(self, x):
		z = torch.ones_like(x)
		for i in range(len(self.mean)):
			z[:,i,:,:] = (x[:,i,:,:] * (self.std[i] + self.eps)) + self.mean[i]
		return z

class MinMaxScaling():
	# works for shape (batchsize, channels, dim1, dim2)
	def __init__(self, x):
		self.min = torch.tensor([torch.min(x[:,i,:,:]) for i in range(x.shape[1])])
		self.max = torch.tensor([torch.max(x[:,i,:,:]) for i in range(x.shape[1])])

	def encode(self, x):
		z = torch.ones_like(x)
		for i in range(len(self.min)):
			z[:,i,:,:] = (x[:,i,:,:] - self.min[i])/(self.max[i] - self.min[i])
		return z

	def decode(self, x): 
		z = torch.ones_like(x)
		for i in range(len(self.min)):
			z[:,i,:,:] = (x[:,i,:,:] * (self.max[i] - self.min[i])) +  self.min[i]
		return z
