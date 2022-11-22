import torch
import torch.nn as nn
from generator_models.FNO import FNOBlock2d

class Generator(nn.Module):
	"""
		Picks up the network from the generator models: FNO, UNet, ...
		also acts as a wrapper function
	"""
	def __init__(self, modes=20, width=32, num_heads=1):
		super().__init__()
		self.network = FNOBlock2d(modes,modes, width, num_heads)
	
	def forward(self,x):
		x = self.network(x)
		return x#.squeeze()

class Discriminator(nn.Module):
	"""
		PatchGAN network that evaluates pxp patch in the field as real or fake.
		It takes the input and the target image and returns a 2D probability field, where each pixel gives the probability that the 
		corresponding pxp patch is real.

		Warning -
		- works for default psize only.
		- works for 1 stress component (num_heads=1) only
	"""

	def __init__(self,psize=70,num_heads=1):
		super().__init__()
		'''
			Unlike original PatchGAN, we are not using padding. Therefore, the output fields are smaller than in the original paper.
		'''
		if psize == 70:
			self.conv1 = nn.Conv2d(3+num_heads,64,4,stride=2,padding=0)
			self.BN1 = nn.BatchNorm2d(64)
			self.conv2 = nn.Conv2d(64,128,4,stride=2,padding=0)
			self.BN2 = nn.BatchNorm2d(128)
			self.conv3 = nn.Conv2d(128,256,4,stride=2,padding=0)
			self.BN3 = nn.BatchNorm2d(256)
			self.conv4 = nn.Conv2d(256,512,4,stride=1,padding=0)
			self.BN4 = nn.BatchNorm2d(512)
			self.conv5 = nn.Conv2d(512,1,4,stride=1,padding=0)
			self.BN5 = nn.BatchNorm2d(1)

		self.leakyrelu = nn.LeakyReLU()

	def forward(self,inp,target):
		tmp = torch.cat((inp,target),dim=-3)		## (3x256x256),(5x256x256)-->(8x256x256)

		tmp = self.conv1(tmp)
		tmp = self.BN1(tmp)
		tmp = self.leakyrelu(tmp)

		tmp = self.conv2(tmp)
		tmp = self.BN2(tmp)
		tmp = self.leakyrelu(tmp)

		tmp = self.conv3(tmp)
		tmp = self.BN3(tmp)
		tmp = self.leakyrelu(tmp)

		tmp = self.conv4(tmp)
		tmp = self.BN4(tmp)
		tmp = self.leakyrelu(tmp)

		tmp = self.conv5(tmp)
		tmp = self.BN5(tmp)
		tmp = self.leakyrelu(tmp)

		return tmp

def GeneratorLoss(generated_output, target_field, disc_generated_field, LAMBDA=100):
	BCElogits = nn.BCEWithLogitsLoss()
	L1loss = nn.L1Loss()
	
	L1 = L1loss(generated_output,target_field)
	g = BCElogits(torch.ones_like(disc_generated_field),disc_generated_field)
	
	gen_loss = g + L1*LAMBDA
	
	return gen_loss, g, L1

def DiscriminatorLoss(disc_generated_field, disc_target_field):
	BCElogits = nn.BCEWithLogitsLoss()
	
	generated_loss = BCElogits(torch.zeros_like(disc_generated_field),disc_generated_field)
	real_loss = BCElogits(torch.ones_like(disc_target_field),disc_target_field)

	disc_loss = generated_loss+real_loss

	return disc_loss, generated_loss, real_loss