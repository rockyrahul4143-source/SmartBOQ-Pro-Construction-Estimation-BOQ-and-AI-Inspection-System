# SmartBOQ Pro — ML Model Weights

> ⚠️ Model files are NOT included in this repository (too large for GitHub).
> Download them from the link below and place them in this folder.

## 📥 Download Trained Models

**Google Drive Link:** *(Upload your .h5 files to Google Drive and paste link here)*

Or train them yourself — see instructions below.

Place your trained model weight files here.

## Required Files

| File | Source Notebook | Framework | Purpose |
|------|----------------|-----------|---------|
| `concrete_crack.h5` | `concrete-crack-image-detection.ipynb` | TensorFlow/Keras | Binary crack detection CNN |
| `resnet50_crack.h5` | `99-9-acc-resnet50-inceptionv3-vgg16.ipynb` | Keras | Ensemble member 1 |
| `inceptionv3_crack.h5` | `99-9-acc-resnet50-inceptionv3-vgg16.ipynb` | Keras | Ensemble member 2 |
| `vgg16_crack.h5` | `99-9-acc-resnet50-inceptionv3-vgg16.ipynb` | Keras | Ensemble member 3 |
| `road_damage.pt` | `road-damage-and-pothole-detection.ipynb` | PyTorch | Faster R-CNN detector |
| `efficientnetb7_safety.h5` | `ensuring-building-safety-using-efficientnets.ipynb` | Keras | Building safety EfficientNet |

## Export Commands

### Keras models
```python
# At end of your Jupyter notebook training cell:
model.save("path/to/smartboq-pro/backend/ml_models/concrete_crack.h5")
```

### PyTorch model (road damage)
```python
import torch
torch.save(model.state_dict(), "path/to/smartboq-pro/backend/ml_models/road_damage.pt")
```

## Without Model Weights

The API still works — it returns a `model_weights_not_found` response with instructions.
No errors are thrown. The frontend shows a "Model Not Loaded" warning with setup steps.

## Install AI Dependencies

Uncomment the AI lines in `requirements.txt`, then:
```bash
pip install tensorflow==2.16.1
pip install torch==2.3.0 torchvision==0.18.0
```

Or for GPU support follow the PyTorch/TensorFlow GPU installation guides.
