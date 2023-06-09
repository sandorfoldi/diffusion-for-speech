import argparse
import glob
import os
from pathlib import Path

import hydra
import pytorch_lightning as pl
import torch
import torchaudio as T
import yaml
from hydra.utils import get_original_cwd
from omegaconf import DictConfig, OmegaConf
from tqdm import tqdm

from diffspeak.utils.technical_utils import load_obj
from diffspeak.utils.utils import set_seed


def synthesize_audio(cfg: DictConfig) -> None:
    """
    Run pytorch-lightning model inference
    Args:
        cfg: hydra config
    Returns:
        None
    """
    set_seed(cfg.training.seed)

    save_path = Path(cfg.inference.audio_path)
    save_path.mkdir(parents=True, exist_ok=True)

    dataloader = load_dataloader(cfg)
    lit_model = load_model(cfg)

    print(
        f"### Starting the synthesis, unconditional is {cfg.datamodule.params.unconditional}"
    )

    with torch.no_grad():
        if cfg.datamodule.params.unconditional:
            for i in tqdm(range(cfg.inference.n_audiofiles)):
                input = {"spectrogram": None, "lang": None}
                audio = lit_model(input)
                path = save_path / f"audio_{i}.wav"
                T.save(path, audio, cfg.datamodule.preprocessing.sample_rate)
        else:
            loggers = []
            trainer = pl.Trainer(
                logger=loggers,
                callbacks=[],
                **cfg.trainer,
            )
            trainer.predict(lit_model, dataloaders=[dataloader])


def load_dataloader(cfg):
    dataloader = None

    if not cfg.datamodule.params.unconditional:
        dataloader = load_obj(cfg.datamodule.datamodule_name)(cfg=cfg)
        dataloader.setup(inference=True)
        dataloader = dataloader.inference_dataloader()

    print(f"### Loaded the dataloader: {dataloader}")
    return dataloader


def load_model(cfg):
    model_name = (
        Path(cfg.inference.run_path) / "saved_models" / cfg.inference.checkpoint_name
    )
    lit_model = load_obj(cfg.training.lightning_module_name).load_from_checkpoint(
        checkpoint_path=model_name, cfg=cfg
    )
    print(f"### Loaded the model")

    return lit_model


@hydra.main(config_path="../configs", config_name="config_synthesis")
def main(cfg: DictConfig):
    # SUPER DIRTY
    cfg.model.params.hop_samples = 256
    cfg.datamodule.path_to_metadata = (
        Path(get_original_cwd()) / cfg.datamodule.path_to_metadata
    )

    if cfg.inference.device == "gpu":
        cfg.trainer.accelerator = "gpu"
        cfg.trainer.gpus = 1

    print(OmegaConf.to_yaml(cfg))
    synthesize_audio(cfg)


if __name__ == "__main__":
    main()
