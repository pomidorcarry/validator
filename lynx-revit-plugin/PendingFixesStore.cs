using System.Collections.Generic;

namespace LynxRevitPlugin
{
    public static class PendingFixesStore
    {
        public static List<FixInstruction> Fixes { get; set; }
    }
}
