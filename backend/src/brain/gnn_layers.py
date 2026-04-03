"""
gnn_layers.py
GNN architecture for multi-intersection traffic control.

Key change vs. original:
  TrafficGNNWithHead.forward() accepts an optional `node_mask`
  boolean tensor. When provided, the loss computed upstream will
  only back-propagate through active (unmasked) nodes, enabling
  correct multi-city training from a unified node set.

GATConv requires 2-D input (num_nodes, features) — never 3-D.
torch._dynamo errors are suppressed at import time so that
Windows multiprocessing re-imports do not crash.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

# Suppress dynamo compilation errors on Windows spawn workers
try:
    torch._dynamo.config.suppress_errors = True
except Exception:
    pass

from torch_geometric.nn import GATConv


# ============================================================
# GNN Encoder  (GAT-based)
# ============================================================

class TrafficGNNEncoder(nn.Module):

    def __init__(self, in_channels: int, hidden_dim: int = 128, out_dim: int = 64):
        super().__init__()

        # heads=2, concat → hidden_dim * 2 features after conv1
        self.conv1 = GATConv(in_channels,    hidden_dim, heads=2, concat=True)
        self.conv2 = GATConv(hidden_dim * 2, out_dim,    heads=1, concat=False)
        self.norm1 = nn.LayerNorm(hidden_dim * 2)
        self.norm2 = nn.LayerNorm(out_dim)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        x          : (N, in_channels)   — MUST be 2-D
        edge_index : (2, E)
        returns    : (N, out_dim)
        """
        assert x.dim() == 2, (
            f"GATConv requires 2-D input; got shape {x.shape}. "
            "Never pass a batched 3-D tensor directly."
        )

        x = self.conv1(x, edge_index)
        x = self.norm1(x)
        x = F.elu(x)

        x = self.conv2(x, edge_index)
        x = self.norm2(x)

        return x


# ============================================================
# Policy / Q-value Head
# ============================================================

class TrafficPolicyHead(nn.Module):

    def __init__(self, in_dim: int, num_actions: int):
        super().__init__()

        self.fc1 = nn.Linear(in_dim, 64)
        self.fc2 = nn.Linear(64,     num_actions)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(x))
        return self.fc2(x)


# ============================================================
# Full Model  (Encoder + Head)
# ============================================================

class TrafficGNNWithHead(nn.Module):

    def __init__(
        self,
        in_channels : int,
        hidden_dim  : int,
        gnn_out_dim : int,
        num_actions : int,
    ):
        super().__init__()

        self.encoder = TrafficGNNEncoder(
            in_channels = in_channels,
            hidden_dim  = hidden_dim,
            out_dim     = gnn_out_dim,
        )

        self.head = TrafficPolicyHead(
            in_dim      = gnn_out_dim,
            num_actions = num_actions,
        )

    def forward(
        self,
        x          : torch.Tensor,
        edge_index : torch.Tensor,
        node_mask  : torch.Tensor = None,   # (N,) bool — active nodes
    ):
        """
        Returns
        -------
        logits     : (N, num_actions)
        embeddings : (N, gnn_out_dim)

        node_mask is NOT applied inside forward — the agent uses it
        externally to zero-out the loss for absent nodes, which keeps
        gradients clean without modifying graph topology.
        """
        embeddings = self.encoder(x, edge_index)   # (N, gnn_out_dim)
        logits     = self.head(embeddings)          # (N, num_actions)

        return logits, embeddings