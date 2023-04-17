"""
This file contains functions and wrappers for loading/creating SpritesWorldDataset.
The sole purpose of this file is to make train.py more readable.
"""
import os

import torch
import tqdm
from torchvision import transforms as transforms

from src import config, data


def dump_generated_dataset(dataset: torch.utils.data.TensorDataset, path: str):
    """Dumps generated dataset as torch tensors to a directory."""
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, "images"), exist_ok=True)
    os.makedirs(os.path.join(path, "latents"), exist_ok=True)

    images = torch.Tensor(len(dataset), 3, 64, 64)
    latents = torch.Tensor(len(dataset), 2, 5)
    for i, (image, latent) in tqdm.tqdm(enumerate(dataset)):
        images[i] = image
        latents[i] = latent
    torch.save(images, os.path.join(path, "images", "images.pt"))
    torch.save(latents, os.path.join(path, "latents", "latents.pt"))


class PreGeneratedDataset(torch.utils.data.Dataset):
    """Loads pre-generated SpriteWorldDataset from a directory."""

    def __init__(self, path: str):
        self.path = path
        self.images = torch.load(os.path.join(path, "images", "images.pt"))
        self.latents = torch.load(os.path.join(path, "latents", "latents.pt"))

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        return self.images[idx], self.latents[idx]


def load_identifiability_dataset(path: str, min_offset, scale):
    """Loads identifiability dataset from a directory."""

    dataset = PreGeneratedDataset(path)

    dataloader = torch.utils.data.DataLoader(
        dataset,
        batch_size=128,
        shuffle=False,
        collate_fn=lambda b: collate_fn_normalizer(b, min_offset, scale),
    )
    print(f"Identifiability dataset successfully loaded from {path}.")
    return dataloader


class SpritesWorldDataWrapper:
    """Wrapper for easy access to train/test loaders for SpritesWorldDataset only."""

    def __init__(self, path, load, save):
        self.path = path
        self.__identifiability_path = None
        self.load = load
        self.save = save
        self.config = config.SpriteWorldConfig()
        self.__scale = None
        self.__min_offset = None

    @property
    def scale(self):
        if self.__scale is None:
            scale = torch.FloatTensor(
                [rng.max - rng.min for rng in self.config.get_ranges().values()]
            ).reshape(1, 1, -1)
            # excluding fixed latents (rotation and two colour channels)
            scale = torch.cat([scale[:, :, :-4], scale[:, :, -3:-2]], dim=-1)
            self.__scale = scale

        return self.__scale

    @property
    def min_offset(self):
        if self.__min_offset is None:
            min_offset = torch.FloatTensor(
                [rng.min for rng in self.config.get_ranges().values()]
            ).reshape(1, 1, -1)
            # excluding fixed latents (rotation and two colour channels)
            min_offset = torch.cat(
                [min_offset[:, :, :-4], min_offset[:, :, -3:-2]], dim=-1
            )
            self.__min_offset = min_offset

        return self.__min_offset

    def get_train_loader(
        self,
        n_samples_train,
        n_slots,
        sample_mode_train,
        delta,
        no_overlap,
        batch_size,
        **kwargs,
    ):
        if self.load and os.path.isdir(os.path.join(self.path, "train")):
            train_dataset = PreGeneratedDataset(os.path.join(self.path, "train"))
            print(
                f"Train dataset successfully loaded from {os.path.join(self.path, 'train')}."
            )
        else:
            train_dataset = data.SpriteWorldDataset(
                n_samples_train,
                n_slots,
                self.config,
                sample_mode=sample_mode_train,
                delta=delta,
                no_overlap=no_overlap,
                transform=transforms.Compose([transforms.ToTensor()]),
            )
            if self.save:
                dump_generated_dataset(train_dataset, os.path.join(self.path, "train"))

        train_loader = torch.utils.data.DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            collate_fn=lambda b: collate_fn_normalizer(b, self.min_offset, self.scale),
        )

        return train_loader

    def get_test_id_loader(
        self,
        n_samples_test,
        n_slots,
        sample_mode_test_id,
        delta,
        no_overlap,
        batch_size,
        **kwargs,
    ):
        if self.load and os.path.isdir(os.path.join(self.path, "test_id")):
            test_dataset = PreGeneratedDataset(os.path.join(self.path, "test_id"))
            print(
                f"Test ID dataset successfully loaded from {os.path.join(self.path, 'test_id')}."
            )
        else:
            test_dataset = data.SpriteWorldDataset(
                n_samples_test,
                n_slots,
                self.config,
                sample_mode=sample_mode_test_id,
                delta=delta,
                no_overlap=no_overlap,
                transform=transforms.Compose([transforms.ToTensor()]),
            )
            if self.save:
                dump_generated_dataset(test_dataset, os.path.join(self.path, "test_id"))

        test_loader = torch.utils.data.DataLoader(
            test_dataset,
            batch_size=batch_size,
            shuffle=False,
            collate_fn=lambda b: collate_fn_normalizer(b, self.min_offset, self.scale),
        )

        return test_loader

    def get_test_ood_loader(
        self,
        n_samples_test,
        n_slots,
        sample_mode_test_ood,
        delta,
        no_overlap,
        batch_size,
        **kwargs,
    ):
        if self.load and os.path.isdir(os.path.join(self.path, "test_ood")):
            test_dataset = PreGeneratedDataset(os.path.join(self.path, "test_ood"))
            print(
                f"Test OOD dataset successfully loaded from {os.path.join(self.path, 'test_ood')}."
            )
        else:
            test_dataset = data.SpriteWorldDataset(
                n_samples_test,
                n_slots,
                self.config,
                sample_mode=sample_mode_test_ood,
                delta=delta,
                no_overlap=no_overlap,
                transform=transforms.Compose([transforms.ToTensor()]),
            )
            if self.save:
                dump_generated_dataset(
                    test_dataset, os.path.join(self.path, "test_ood")
                )

        test_loader = torch.utils.data.DataLoader(
            test_dataset,
            batch_size=batch_size,
            shuffle=False,
            collate_fn=lambda b: collate_fn_normalizer(b, self.min_offset, self.scale),
        )

        return test_loader

    @property
    def identifiability_path(self):
        return self.__identifiability_path

    @identifiability_path.setter
    def identifiability_path(self, value):
        if self.__identifiability_path is None:
            self.__identifiability_path = value
        else:
            raise ValueError("Identifiability path already set.")

    def get_identifiability_train_loader(self, sample_mode_train, **kwargs):
        if self.identifiability_path is None:
            raise ValueError("Identifiability path not set.")
        return load_identifiability_dataset(
            os.path.join(self.identifiability_path, sample_mode_train, "train"),
            self.min_offset,
            self.scale,
        )

    def get_identifiability_test_id_loader(self, sample_mode_test_id, **kwargs):
        if self.identifiability_path is None:
            raise ValueError("Identifiability path not set.")
        return load_identifiability_dataset(
            os.path.join(self.identifiability_path, sample_mode_test_id, "test_id"),
            self.min_offset,
            self.scale,
        )

    def get_identifiability_test_ood_loader(self, sample_mode_test_ood, **kwargs):
        if self.identifiability_path is None:
            raise ValueError("Identifiability path not set.")
        return load_identifiability_dataset(
            os.path.join(self.identifiability_path, sample_mode_test_ood, "test_ood"),
            self.min_offset,
            self.scale,
        )


def collate_fn_normalizer(batch, bias=0, scale=1):
    """Normalize latents target to [0, 1]. Used in dataloader."""
    images, latents = zip(*batch)
    latents = torch.stack(latents)
    latents = (latents - bias) / scale
    return torch.stack(images), latents
