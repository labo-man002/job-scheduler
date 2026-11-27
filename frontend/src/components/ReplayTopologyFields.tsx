import { Button } from "@/components/ui/button";

type Uplink = { leaf: number; spine: number };
type Attachment = { node: number; leaf: number };
type LeafSpine = { kind: "leaf_spine"; leaves: number[]; uplinks: Uplink[]; attachments: Attachment[] };

export type ReplayTopology = { kind: "linear" } | LeafSpine;

function fabricPreset(nodeIds: number[]): LeafSpine {
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

function switchIds(existing: number[], count: number) {
  const ids = existing.slice(0, count);
  for (let id = 1; ids.length < count; id += 1) {
    if (!ids.includes(id)) ids.push(id);
  }
  return ids;
}

export function ReplayTopologyFields({ nodeIds, value, onChange }: {
  nodeIds: number[];
  value: ReplayTopology;
  onChange: (value: ReplayTopology) => void;
}) {
  return <div className="space-y-4">
    <label className="flex flex-wrap items-center gap-3 text-sm font-medium">
      Topology
      <select className="rounded-md border bg-background px-3 py-2" value={value.kind}
        onChange={event => onChange(event.target.value === "linear" ? { kind: "linear" } : fabricPreset(nodeIds))}>
        <option value="linear">Linear</option>
        <option value="leaf_spine">Leaf-spine</option>
      </select>
    </label>
    {value.kind === "leaf_spine" &&
      <LeafSpineFields nodeIds={nodeIds} value={value} onChange={onChange} />
    }
  </div>;
}

function LeafSpineFields({ nodeIds, value, onChange }: {
  nodeIds: number[];
  value: LeafSpine;
  onChange: (value: LeafSpine) => void;
}) {
  const spineIds = switchIds([...new Set(value.uplinks.map(link => link.spine))], 4).sort((a, b) => a - b);

  function changeLeafCount(count: number) {
    const leaves = switchIds(value.leaves, count);
    onChange({
      ...value,
      leaves,
      uplinks: value.uplinks.filter(link => leaves.includes(link.leaf)),
      attachments: value.attachments.map(link => leaves.includes(link.leaf) ? link : { ...link, leaf: leaves[0] }),
    });
  }

  function changeUplink(leaf: number, spine: number, enabled: boolean) {
    const uplinks = value.uplinks.filter(link => link.leaf !== leaf || link.spine !== spine);
    if (enabled) uplinks.push({ leaf, spine });
    onChange({ ...value, uplinks });
  }

  return <div className="space-y-4 border-t pt-4">
    <div className="flex flex-wrap items-center gap-3">
      <label className="text-sm font-medium">Leaf switches
        <select className="ml-2 rounded border bg-background p-1" value={value.leaves.length}
          onChange={event => changeLeafCount(Number(event.target.value))}>
          {[1, 2, 3, 4].map(count => <option key={count}>{count}</option>)}
        </select>
      </label>
      <Button type="button" size="sm" variant="outline" onClick={() => onChange(fabricPreset(nodeIds))}>
        Restore fabric preset
      </Button>
    </div>
    <fieldset className="flex flex-wrap gap-3">
      <legend className="pb-2 text-sm font-medium">Node attachments</legend>
      {nodeIds.map(node => (
        <label className="text-sm" key={node}>Node {node} leaf
          <select className="ml-2 rounded border bg-background p-1"
            value={value.attachments.find(link => link.node === node)?.leaf ?? value.leaves[0]}
            onChange={event => {
              const leaf = Number(event.target.value);
              onChange({
                ...value,
                attachments: value.attachments.map(link => link.node === node ? { node, leaf } : link),
              });
            }}>
            {value.leaves.map(leaf => <option key={leaf} value={leaf}>{leaf}</option>)}
          </select>
        </label>
      ))}
    </fieldset>
    <fieldset className="space-y-2">
      <legend className="pb-2 text-sm font-medium">Spine uplinks</legend>
      <div className="overflow-x-auto">
        <table className="border-collapse text-left text-sm">
          <thead>
            <tr>
              <th scope="col" className="px-2 py-1">Leaf</th>
              {spineIds.map(spine => <th key={spine} scope="col" className="px-2 py-1">Spine {spine}</th>)}
            </tr>
          </thead>
          <tbody>
            {value.leaves.map(leaf => (
              <tr key={leaf} className="border-t">
                <th scope="row" className="px-2 py-1">{leaf}</th>
                {spineIds.map(spine => (
                  <td key={spine} className="px-2 py-1">
                    <input type="checkbox" className="size-4 accent-primary" aria-label={`Leaf ${leaf} to spine ${spine}`}
                      checked={value.uplinks.some(link => link.leaf === leaf && link.spine === spine)}
                      onChange={event => changeUplink(leaf, spine, event.target.checked)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-muted-foreground">
        Remove uplinks to test whether a job can still reach enough GPUs. Job durations stay fixed.
      </p>
    </fieldset>
  </div>;
}
