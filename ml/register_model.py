"""Register trained model into ModelRegistry."""
from __future__ import annotations
import os
from ..model_registry import ModelRegistry


def register(joblib_path: str = None, onnx_path: str = None, name: str = "mobile_money_fraud_v1"):
    mr = ModelRegistry()
    if onnx_path and os.path.exists(onnx_path):
        mr.load_onnx(name, onnx_path, version=os.path.basename(onnx_path))
        print(f"Registered ONNX model at {onnx_path}")
    elif joblib_path and os.path.exists(joblib_path):
        mr.load_joblib(name, joblib_path, version=os.path.basename(joblib_path))
        print(f"Registered joblib model at {joblib_path}")
    else:
        raise FileNotFoundError("No model file found to register")


if __name__ == "__main__":
    import sys
    jb = sys.argv[1] if len(sys.argv) > 1 else None
    onx = sys.argv[2] if len(sys.argv) > 2 else None
    register(joblib_path=jb, onnx_path=onx)
