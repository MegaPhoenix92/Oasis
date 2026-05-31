using System;
using System.Collections.Generic;

namespace Oasis.Persistence
{
    [Serializable]
    public sealed class OasisCreatorOperation
    {
        public string type; // "place", "move", "delete"
        public OasisWorldObject snapshot; // for place and delete
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
    }
}
