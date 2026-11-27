type Uplink = { leaf: number; spine: number };
type Attachment = { node: number; leaf: number };
export type LeafSpine = { kind: "leaf_spine"; leaves: number[]; uplinks: Uplink[]; attachments: Attachment[] };

export type ReplayTopology = { kind: "linear" } | LeafSpine;

export function fabricPreset(nodeIds: number[]): LeafSpine {
  const leaves = nodeIds.length > 1 ? [1, 2] : [1];
  return {
    kind: "leaf_spine",
    leaves,
    uplinks: leaves.map(leaf => ({ leaf, spine: 1 })),
    attachments: nodeIds.map((node, index) => ({ node, leaf: leaves[index % leaves.length] })),
  };
}

export function resizeReplayTopology(value: ReplayTopology, nodeIds: number[]): ReplayTopology {
  if (value.kind === "linear") return value;
  return {
    ...value,
    attachments: nodeIds.map((node, index) =>
      value.attachments.find(attachment => attachment.node === node)
      ?? { node, leaf: value.leaves[index % value.leaves.length] },
    ),
  };
}
