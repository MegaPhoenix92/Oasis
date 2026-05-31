using System;
using System.Collections.Generic;

namespace Oasis.Persistence
{
    [Serializable]
    public sealed class OasisCreatorOperation
    {
        public string type; // "place", "move", "delete", "refine"
        public OasisWorldObject snapshot; // for place and delete
        public OasisWorldObject before; // for refine
        public OasisWorldObject after; // for refine
        public string instance_id; // for move
        public OasisWorldTransform from; // for move
        public OasisWorldTransform to; // for move
    }

    public sealed class OasisCreatorHistory
    {
        private readonly Stack<OasisCreatorOperation> undoStack = new Stack<OasisCreatorOperation>();
        private readonly Stack<OasisCreatorOperation> redoStack = new Stack<OasisCreatorOperation>();

        public int UndoCount => undoStack.Count;
        public int RedoCount => redoStack.Count;

        public void PushOperation(OasisCreatorOperation op)
        {
            if (op == null) return;
            undoStack.Push(op);
            redoStack.Clear();
        }

        public OasisCreatorOperation PopUndo()
        {
            if (undoStack.Count == 0) return null;
            OasisCreatorOperation op = undoStack.Pop();
            redoStack.Push(op);
            return op;
        }

        public OasisCreatorOperation PopRedo()
        {
            if (redoStack.Count == 0) return null;
            OasisCreatorOperation op = redoStack.Pop();
            undoStack.Push(op);
            return op;
        }

        public void Clear()
        {
            undoStack.Clear();
            redoStack.Clear();
        }

        public bool ReferencesAsset(string assetId)
        {
            if (string.IsNullOrWhiteSpace(assetId)) return false;
            return StackReferencesAsset(undoStack, assetId) || StackReferencesAsset(redoStack, assetId);
        }

        private static bool StackReferencesAsset(Stack<OasisCreatorOperation> stack, string assetId)
        {
            foreach (OasisCreatorOperation op in stack)
            {
                if (op == null) continue;
                if (op.snapshot != null && op.snapshot.asset_id == assetId) return true;
                if (op.before != null && op.before.asset_id == assetId) return true;
                if (op.after != null && op.after.asset_id == assetId) return true;
            }
            return false;
        }
    }
}
