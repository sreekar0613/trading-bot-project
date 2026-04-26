import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pause, Play } from "lucide-react";
import { getBotStatus, pauseBot, resumeBot } from "@/services/api";

export function PauseToggle() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["bot-status"],
    queryFn: getBotStatus,
    refetchInterval: 15_000,
  });

  const paused = !!data?.paused;

  const mutation = useMutation({
    mutationFn: () => (paused ? resumeBot() : pauseBot()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bot-status"] });
    },
  });

  return (
    <button
      type="button"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className="inline-flex h-9 items-center gap-2 rounded-input border border-border bg-surface px-3 text-sm font-medium text-text-primary transition-colors hover:bg-bg disabled:opacity-50"
    >
      {mutation.isPending ? (
        <Loader2 size={14} className="animate-spin" />
      ) : paused ? (
        <Play size={14} />
      ) : (
        <Pause size={14} />
      )}
      {paused ? "Resume" : "Pause New Entries"}
    </button>
  );
}
