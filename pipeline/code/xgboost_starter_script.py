import argparse
import json
import os
import pickle
import sys

import pandas as pd
import xgboost as xgb
from sagemaker.session import Session
# from sagemaker.experiments.run import load_run
# import boto3

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Hyperparameters are described here
    parser.add_argument("--num_round", type=int, default=999)
    parser.add_argument("--max_depth", type=int, default=3)
    parser.add_argument("--eta", type=float, default=0.2)
    parser.add_argument("--objective", type=str, default="binary:logistic")
    parser.add_argument("--nfold", type=int, default=5)
    parser.add_argument("--early_stopping_rounds", type=int, default=10)
    parser.add_argument("--train_data_path", type=str, default=os.environ.get("SM_CHANNEL_TRAIN"))

    # SageMaker specific arguments. Defaults are set in the environment variables.
    parser.add_argument("--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR"))
    parser.add_argument("--output-data-dir", type=str, default=os.environ.get("SM_OUTPUT_DATA_DIR"))
    parser.add_argument("--region", type=str, default="us-east-2", help="SageMaker Region")


    args = parser.parse_args()
    
    # session = Session(boto3.session.Session(region_name=args.region))
    # with load_run(sagemaker_session=session) as run:

    data = pd.read_csv(f"{args.train_data_path}/train.csv")
    train = data.drop("anomaly", axis=1)
    label = pd.DataFrame(data["anomaly"])
    dtrain = xgb.DMatrix(train, label=label)

    # run.log_parameter("num_train_samples",  len(train.index))

    params = {"max_depth": args.max_depth, "eta": args.eta, "objective": args.objective}
    num_boost_round = args.num_round
    nfold = args.nfold
    early_stopping_rounds = args.early_stopping_rounds

    cv_results = xgb.cv(
        params=params,
        dtrain=dtrain,
        num_boost_round=num_boost_round,
        nfold=nfold,
        early_stopping_rounds=early_stopping_rounds,
        metrics=("auc"),
        seed=0,
    )

    print(f"[0]#011train-auc:{cv_results.iloc[-1]['train-auc-mean']}")
    #print(f"[1]#011train-auc std:{cv_results.iloc[-1]['train-auc-std']}")
    print(f"[1]#011validation-auc:{cv_results.iloc[-1]['test-auc-mean']}")
    #print(f"[1]#011validation-auc std:{cv_results.iloc[-1]['test-auc-std']}")

#     run.log_metric(name="Train-AUC", value=cv_results.iloc[-1]['train-auc-mean'])
#     run.log_metric(name="Train-Std", value=cv_results.iloc[-1]['train-auc-std'])

#     run.log_metric(name="Validation-AUC", value=cv_results.iloc[-1]['test-auc-mean'])
#     run.log_metric(name="Validation-Std", value=cv_results.iloc[-1]["test-auc-std"])

    metrics_data = {
        "binary_classification_metrics": {
            "validation:auc": {
                "value": cv_results.iloc[-1]["test-auc-mean"],
                "standard_deviation": cv_results.iloc[-1]["test-auc-std"]
            },
            "train:auc": {
                "value": cv_results.iloc[-1]["train-auc-mean"],
                "standard_deviation": cv_results.iloc[-1]["train-auc-std"]
            },
        }
    }
    model = xgb.train(params=params, dtrain=dtrain, num_boost_round=len(cv_results))

    # Save the model to the location specified by ``model_dir``
    metrics_location = args.output_data_dir + "/metrics.json"
    model_location = args.model_dir + "/xgboost-model"

    with open(metrics_location, "w") as f:
        json.dump(metrics_data, f)

    with open(model_location, "wb") as f:
        pickle.dump(model, f)


def model_fn(model_dir):
    with open(os.path.join(model_dir, "xgboost-model"), "rb") as f:
        booster = pickle.load(f)
    return booster