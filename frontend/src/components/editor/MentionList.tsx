import React, {
  useState,
  useEffect,
  forwardRef,
  useImperativeHandle,
} from "react";
import { SuggestionKeyDownProps } from "@tiptap/suggestion";

interface MentionListProps {
  items: { id: string; name: string; type: string }[];
  command: (item: { id: string; name: string; type: string }) => void;
}

export interface MentionListRef {
  onKeyDown: (props: SuggestionKeyDownProps) => boolean;
}

export const MentionList = forwardRef<MentionListRef, MentionListProps>(
  (props, ref) => {
    const [selectedIndex, setSelectedIndex] = useState(0);

    const selectItem = (index: number) => {
      const item = props.items[index];
      if (item) {
        props.command(item);
      }
    };

    const upHandler = () => {
      setSelectedIndex(
        (selectedIndex + props.items.length - 1) % props.items.length
      );
    };

    const downHandler = () => {
      setSelectedIndex((selectedIndex + 1) % props.items.length);
    };

    const enterHandler = () => {
      selectItem(selectedIndex);
    };

    useEffect(() => setSelectedIndex(0), [props.items]);

    useImperativeHandle(ref, () => ({
      onKeyDown: (props: SuggestionKeyDownProps) => {
        if (props.event.key === "ArrowUp") {
          upHandler();
          return true;
        }
        if (props.event.key === "ArrowDown") {
          downHandler();
          return true;
        }
        if (props.event.key === "Enter") {
          enterHandler();
          return true;
        }
        return false;
      },
    }));

    return (
      <div className="bg-card border border-border rounded-md shadow-lg p-2">
        {props.items.length ? (
          props.items.map((item, index) => (
            <button
              key={item.id}
              className={`flex items-center w-full text-left px-2 py-1 rounded-md text-sm ${
                index === selectedIndex
                  ? "bg-primary text-primary-foreground"
                  : ""
              }`}
              onClick={() => selectItem(index)}
            >
              <span className="font-semibold">{item.name}</span>
              <span className="text-xs text-muted-foreground ml-2">
                ({item.type})
              </span>
            </button>
          ))
        ) : (
          <div className="p-2 text-sm text-muted-foreground">No results</div>
        )}
      </div>
    );
  }
);

MentionList.displayName = "MentionList";
