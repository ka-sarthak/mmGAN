import torch
import os, psutil
import json
import time
from torch.nn import L1Loss 
from models.UNet import UNet
from models.FNO import FNO
from utils.config_module import config
from utils.data_processing import makePathAndDirectories, importDataset, scaleDataset
from utils.utilities import countParameters
from utils.postprocessing import lossPlots

def train():
	## configs and paths
	training_config = config["training"]
	exp_config = config["experiment"]
	exp_name = exp_config["name"]
	
	if exp_config["generator"] == "UNet":
		model_config = config["model"]["UNet"]  
	elif exp_config["generator"] == "FNO":
		model_config = config["model"]["FNO"]
	else:
		raise AssertionError("Unexpected argument for generator.")  

	path_save_model, path_training_log, path_loss_plot = makePathAndDirectories(config)

	## setup logger for continued training or new training
	if exp_config["continueTraining"] == True:
		gcheckpoint = torch.load(path_save_model+f"{exp_name}.pt")
		epoch_completed   = gcheckpoint["epoch_completed"]
		g_loss_training   = gcheckpoint["training_loss"]
		g_loss_validation = gcheckpoint["validation_loss"]
		logfile = open(path_training_log + f"{exp_name}.log", "a")
	else:
		epoch_completed = 0
		g_loss_training   = []
		g_loss_validation = []
		logfile = open(path_training_log + f"{exp_name}.log", "w")

	## import dataset 
	train_data, val_data, _ = importDataset(config["path"]["data"], training_config["trainValTestSplit"], exp_config["outputHeads"])
	
	## get scaled dataset and trained Scaler objects
	x_train, y_train, x_val, y_val, x_scaler, y_scaler = scaleDataset(train_data,val_data,model_config["scaler"])
	print("Shape of the training data (X,y): ", x_train.shape, y_train.shape)
	print("Shape of the validation data (X,y): ", x_val.shape, y_val.shape)

	## define dataloaders, models, and optimizers
	train_loader = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(x_train, y_train), batch_size=training_config["batchSize"], shuffle=True)
	val_loader = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(x_val, y_val), batch_size=training_config["trainValTestSplit"][1], shuffle=False)

	## define the generator model, optimizer, scheduler, loss function
	if exp_config["generator"] == "UNet":
		g_model = UNet(kernel=model_config["kernel"], in_channels=exp_config["inputHeads"], out_channels=exp_config["outputHeads"], version=model_config["version"])
	elif exp_config["generator"] == "FNO":
		g_model = FNO(modes1=model_config["modes1"],modes2=model_config["modes2"],width=model_config["width"],num_heads=exp_config["outputHeads"],version=model_config["version"])
	
	g_optimizer = torch.optim.Adam(g_model.parameters(), lr=training_config["learningRate"], weight_decay=training_config["weightDecay"])
	g_scheduler = torch.optim.lr_scheduler.StepLR(g_optimizer, step_size=training_config["stepSize"], gamma=training_config["gamma"])
	Loss = L1Loss()
	metric = L1Loss()
	
	## load states if continued Training
	if exp_config["continueTraining"] == True:
		g_model.load_state_dict(gcheckpoint['model_state_dict'])
		g_optimizer.load_state_dict(gcheckpoint['optimizer_state_dict'])
		g_scheduler.load_state_dict(gcheckpoint['scheduler_state_dict'])
	
	## logging
	if epoch_completed == 0:
		logfile.write("-----------config-----------\n")
		logfile.write(json.dumps(config,indent=4))
		logfile.write("\n--------------------------------\n")
		countParameters(g_model,logfile)
	
	## training loop
	ep = epoch_completed + 1
	while(ep <= training_config["epochs"] + epoch_completed):
		g_model.train()

		t1 = time.time()
		g_loss_epoch = 0
		for batch_x,batch_target in train_loader:
			g_optimizer.zero_grad()
			
			g_output 	 = g_model(batch_x)
			g_loss_batch = Loss(g_output, batch_target)
			g_loss_epoch +=  g_loss_batch.item()
			g_loss_batch.backward()
			
			g_optimizer.step()
			
		g_scheduler.step()
		t2 = time.time()
		
		# average the losses over all batches
		g_loss_epoch /= len(train_loader)
		g_loss_training.append(g_loss_epoch)

		# computing validation loss
		g_model.eval()
		loss = 0
		for x,target in val_loader:
			g_output = g_model(x).detach()
			g_output = y_scaler.decode(g_output).detach()
			target   = y_scaler.decode(target)
			loss    += metric(g_output,target).item()/1e6
		g_loss_validation.append( loss/len(val_loader))


		logfile.write(f"\nEpoch: {ep}\t Time(s): {t2-t1} \t g_train_loss: {g_loss_epoch}\t g_val_loss: {g_loss_validation[-1]}")
		print(f"{ep} \t t:{t2-t1} \t g_train_loss:{g_loss_epoch} \t g_val_loss:{g_loss_validation[-1]} \t MEM (MB): {psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2}", flush=True)
		
		ep+=1

	## save the model and generate loss plots
	g_model.train()
	torch.save(
		{
			'epoch_completed': ep-1,
			'model_state_dict': g_model.state_dict(),
			'optimizer_state_dict': g_optimizer.state_dict(),
			'scheduler_state_dict': g_scheduler.state_dict(),
			'training_loss': g_loss_training,
			'validation_loss': g_loss_validation
		},
		path_save_model+f"{exp_name}.pt")
	lossPlots(g_loss_training,g_loss_validation,path_loss_plot,exp_name)

	logfile.close()
