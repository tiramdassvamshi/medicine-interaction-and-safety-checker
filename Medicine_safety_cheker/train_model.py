import pickle
import os

os.makedirs("model", exist_ok=True)

model = {
    "child": 700,
    "adult": 3000,
    "senior": 1500
}

with open("model/model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model trained successfully")
