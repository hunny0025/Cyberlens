"""
CyberLens — Siamese Network for Operator Attribution
========================================================
PyTorch Siamese network that learns to identify whether two
Telegram channels are operated by the same person/group.

Takes two 28-dimensional behavioral fingerprints as input and
outputs a similarity score (0-1) via cosine similarity.

Architecture:
    Shared encoder: Linear(28→64) → ReLU → Dropout(0.3) →
                    Linear(64→32) → ReLU → Linear(32→16)
    Output: cosine similarity between encoded representations

Author: CyberLens Team — GPCSSI Internship
"""

import logging
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger("cyberlens.fingerprinting.siamese")


# ---------------------------------------------------------------------------
# Contrastive Loss
# ---------------------------------------------------------------------------

class ContrastiveLoss(nn.Module):
    """Contrastive loss for Siamese network training.

    Pulls same-operator pairs together and pushes different-operator
    pairs apart in embedding space.

    Args:
        margin: Minimum distance for negative pairs. Default: 0.5.
    """

    def __init__(self, margin: float = 0.5):
        super().__init__()
        self.margin = margin

    def forward(
        self,
        similarity: torch.Tensor,
        label: torch.Tensor,
    ) -> torch.Tensor:
        """Compute contrastive loss.

        Args:
            similarity: Cosine similarity scores (0-1). Shape: (batch,).
            label: 1 = same operator, 0 = different operator. Shape: (batch,).

        Returns:
            Scalar loss tensor.
        """
        # Convert similarity to distance (1 - similarity)
        distance = 1.0 - similarity

        # Positive: minimize distance (label=1 → same operator)
        pos_loss = label * distance.pow(2)

        # Negative: maximize distance up to margin (label=0 → different)
        neg_loss = (1.0 - label) * F.relu(self.margin - distance).pow(2)

        return (pos_loss + neg_loss).mean()


# ---------------------------------------------------------------------------
# Shared Encoder
# ---------------------------------------------------------------------------

class FingerprintEncoder(nn.Module):
    """Shared encoder for behavioral fingerprint vectors.

    Maps a 28-dim fingerprint to a 16-dim embedding.

    Architecture:
        Linear(28→64) → ReLU → Dropout(0.3) →
        Linear(64→32) → ReLU → Linear(32→16)
    """

    def __init__(self, input_dim: int = 28, embed_dim: int = 16):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, embed_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode a fingerprint vector.

        Args:
            x: Fingerprint tensor. Shape: (batch, 28).

        Returns:
            Embedding tensor. Shape: (batch, 16).
        """
        return self.network(x)


# ---------------------------------------------------------------------------
# Siamese Network
# ---------------------------------------------------------------------------

class SiameseNetwork(nn.Module):
    """Siamese network for operator attribution.

    Compares two behavioral fingerprints and outputs a similarity
    score indicating the probability that both channels are operated
    by the same person/group.

    Attributes:
        encoder: Shared FingerprintEncoder.
        input_dim: Input feature dimension (28).
        embed_dim: Embedding dimension (16).
    """

    def __init__(self, input_dim: int = 28, embed_dim: int = 16):
        """Initialize the Siamese network.

        Args:
            input_dim: Dimension of input fingerprint vectors.
            embed_dim: Dimension of output embeddings.
        """
        super().__init__()
        self.input_dim = input_dim
        self.embed_dim = embed_dim
        self.encoder = FingerprintEncoder(input_dim, embed_dim)

    def forward(
        self,
        fp1: torch.Tensor,
        fp2: torch.Tensor,
    ) -> torch.Tensor:
        """Compute similarity between two fingerprint vectors.

        Args:
            fp1: First fingerprint. Shape: (batch, 28).
            fp2: Second fingerprint. Shape: (batch, 28).

        Returns:
            Similarity scores (0-1). Shape: (batch,).
        """
        emb1 = self.encoder(fp1)
        emb2 = self.encoder(fp2)
        similarity = F.cosine_similarity(emb1, emb2, dim=1)
        # Clamp to [0, 1]
        return (similarity + 1.0) / 2.0

    def encode(self, fp: torch.Tensor) -> torch.Tensor:
        """Encode a fingerprint into the embedding space.

        Args:
            fp: Fingerprint tensor. Shape: (batch, 28) or (28,).

        Returns:
            Embedding tensor. Shape: (batch, 16) or (16,).
        """
        if fp.dim() == 1:
            fp = fp.unsqueeze(0)
        with torch.no_grad():
            emb = self.encoder(fp)
        return emb.squeeze(0) if emb.shape[0] == 1 else emb

    def similarity_score(
        self,
        fp1_vector: list,
        fp2_vector: list,
        device: Optional[str] = None,
    ) -> float:
        """Convenience method for computing similarity from raw vectors.

        Args:
            fp1_vector: First fingerprint as list of floats (28-dim).
            fp2_vector: Second fingerprint as list of floats (28-dim).
            device: Device string (default: auto-detect).

        Returns:
            Similarity score as float (0-1).
        """
        dev = torch.device(device) if device else next(self.parameters()).device
        t1 = torch.tensor(fp1_vector, dtype=torch.float32).unsqueeze(0).to(dev)
        t2 = torch.tensor(fp2_vector, dtype=torch.float32).unsqueeze(0).to(dev)

        self.eval()
        with torch.no_grad():
            score = self.forward(t1, t2)
        return score.item()

    @classmethod
    def load(
        cls,
        model_path: str,
        device: Optional[str] = None,
        input_dim: int = 28,
        embed_dim: int = 16,
    ) -> "SiameseNetwork":
        """Load a trained model from disk.

        Args:
            model_path: Path to saved state dict (.pth).
            device: Device to load onto.
            input_dim: Input feature dimension.
            embed_dim: Embedding dimension.

        Returns:
            Loaded SiameseNetwork instance.
        """
        dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        model = cls(input_dim=input_dim, embed_dim=embed_dim)
        state_dict = torch.load(model_path, map_location=dev)
        model.load_state_dict(state_dict)
        model.to(dev)
        model.eval()
        logger.info("SiameseNetwork loaded from %s (device=%s)", model_path, dev)
        return model
