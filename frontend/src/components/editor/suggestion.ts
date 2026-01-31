import { ReactRenderer } from "@tiptap/react";
import tippy, { Instance as TippyInstance } from "tippy.js";
import { MentionList, MentionListRef } from "@/components/editor/MentionList";
import { Editor, Range } from "@tiptap/core";
import { SuggestionProps, SuggestionKeyDownProps } from "@tiptap/suggestion";

interface CodexItem {
  id: string;
  name: string;
  type: string;
}

// Update to match what Tiptap expects based on the error message
interface MentionNodeAttrs {
  id: string | null;
  label: string;
}

export const suggestion = {
  // Match the exact signature Tiptap expects
  command: (props: {
    editor: Editor;
    range: Range;
    props: MentionNodeAttrs;
  }) => {
    const { editor, range } = props;
    const mentionProps = props.props; // This is what Tiptap passes

    // We need to check for null id
    const id = mentionProps.id;
    if (id === null) {
      return;
    }

    // Use either the provided label or id
    const label = mentionProps.label || id;

    editor
      .chain()
      .focus()
      .deleteRange(range)
      .insertContent([
        {
          type: "mention",
          attrs: { id, label },
        },
        {
          type: "text",
          text: " ",
        },
      ])
      .run();
  },

  items: ({ query, editor }: { query: string; editor: Editor }) => {
    const codexItems = editor.storage?.codexStorage?.codexItems || [];
    // Transform CodexItems to match what Tiptap expects
    return codexItems
      .filter((item: CodexItem) =>
        item.name.toLowerCase().startsWith(query.toLowerCase())
      )
      .slice(0, 10)
      .map((item: CodexItem) => ({
        id: item.id,
        label: item.name,
        // Include original properties for our component
        name: item.name,
        type: item.type,
      }));
  },

  render: () => {
    let component: ReactRenderer<MentionListRef>;
    let popup: TippyInstance[];

    const getReferenceClientRect = (
      props: SuggestionProps<CodexItem>
    ): DOMRect | null => {
      const rect =
        typeof props.clientRect === "function" ? props.clientRect() : null;
      return rect;
    };

    return {
      onStart: (props: SuggestionProps<CodexItem>) => {
        const rect = getReferenceClientRect(props);
        if (!rect) return;

        component = new ReactRenderer(MentionList, {
          props,
          editor: props.editor,
        });

        popup = tippy("body", {
          getReferenceClientRect: () => rect,
          appendTo: () => document.body,
          content: component.element,
          showOnCreate: true,
          interactive: true,
          trigger: "manual",
          placement: "bottom-start",
        });
      },

      onUpdate(props: SuggestionProps<CodexItem>) {
        component.updateProps(props);

        const rect = getReferenceClientRect(props);
        if (!rect) return;

        popup[0].setProps({
          getReferenceClientRect: () => rect,
        });
      },

      onKeyDown(props: SuggestionKeyDownProps) {
        if (props.event.key === "Escape") {
          popup[0].hide();
          return true;
        }
        return component.ref?.onKeyDown(props) || false;
      },

      onExit() {
        if (popup && popup[0]) {
          popup[0].destroy();
        }
        if (component) {
          component.destroy();
        }
      },
    };
  },
};
