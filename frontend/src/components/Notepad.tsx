import React from "react";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BrainCircuit } from "lucide-react";

interface NotepadProps {
  notepadContent: string;
  setNotepadContent: (content: string) => void;
  onProactiveAssist: () => void;
  isProactiveAssistLoading: boolean;
}

export function Notepad({
  notepadContent,
  setNotepadContent,
  onProactiveAssist,
  isProactiveAssistLoading,
}: NotepadProps) {
  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between py-3 px-4">
        <CardTitle className="text-lg font-semibold">Notepad</CardTitle>
        <Button
          size="sm"
          onClick={onProactiveAssist}
          disabled={isProactiveAssistLoading || !notepadContent.trim()}
          variant="outline"
        >
          <BrainCircuit className="mr-2 h-4 w-4" />
          {isProactiveAssistLoading ? "Thinking..." : "Proactive Assist"}
        </Button>
      </CardHeader>
      <CardContent className="p-0 flex-grow">
        <ScrollArea className="h-full">
          <Textarea
            placeholder="Use this space for brainstorming, jotting down ideas, or pasting text. Then use 'Proactive Assist' to get suggestions based on your notes."
            className="h-full w-full resize-none border-0 rounded-none focus-visible:ring-0"
            value={notepadContent}
            onChange={(e) => setNotepadContent(e.target.value)}
          />
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
