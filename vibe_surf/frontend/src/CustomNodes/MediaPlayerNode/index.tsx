import { NodeResizer } from "@xyflow/react";
import { debounce } from "lodash";
import { useMemo, useRef, useState, useEffect } from "react";
import { MediaDisplay } from "@/components/MediaDisplay";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import useFlowStore from "@/stores/flowStore";
import type { MediaPlayerDataType } from "@/types/flow";

const MIN_WIDTH = 400;
const MIN_HEIGHT = 300;
const MAX_WIDTH = 800;
const MAX_HEIGHT = 600;
const DEFAULT_WIDTH = 500;
const DEFAULT_HEIGHT = 350;

function MediaPlayerNode({
  data,
  selected,
}: {
  data: MediaPlayerDataType;
  selected?: boolean;
}) {
  const nodeDiv = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const [mediaUrl, setMediaUrl] = useState("");
  const [executionMedia, setExecutionMedia] = useState<{
    path: string;
    type: "image" | "video";
    alt?: string;
    showControls?: boolean;
    autoPlay?: boolean;
    loop?: boolean;
  } | null>(null);

  const nodeData = useMemo(
    () => currentFlow?.data?.nodes.find((node) => node.id === data.id),
    [currentFlow, data.id],
  );

  const nodeDataWidth = useMemo(
    () => nodeData?.measured?.width ?? DEFAULT_WIDTH,
    [nodeData?.measured?.width],
  );
  
  const nodeDataHeight = useMemo(
    () => nodeData?.measured?.height ?? DEFAULT_HEIGHT,
    [nodeData?.measured?.height],
  );

  const debouncedResize = useMemo(
    () =>
      debounce((width: number, height: number) => {
        setNode(data.id, (node) => {
          return {
            ...node,
            width: width,
            height: height,
          };
        });
      }, 5),
    [data.id, setNode],
  );

  // Listen to flowPool to get execution results
  useEffect(() => {
    if (!flowPool) return;

    // Get the latest execution result for this node
    const nodeHistory = flowPool[data.id] ?? [];
    const lastExecution = nodeHistory[nodeHistory.length - 1];
    
    if (lastExecution?.data?.outputs) {
      const outputs = lastExecution.data.outputs;
      
      for (const outputName in outputs) {
        const output = outputs[outputName];
        const resultMessage = output?.message;
        
        if (!resultMessage) continue;

        let mediaData: any = null;
        
        // Case 1: Message with data.type (Standard Message)
        if (resultMessage.data?.type &&
            ["image", "video"].includes(resultMessage.data.type)) {
          mediaData = resultMessage.data;
        }
        // Case 2: Direct object (Data)
        else if (resultMessage.type &&
                 ["image", "video"].includes(resultMessage.type)) {
          mediaData = resultMessage;
        }
        // Case 3: Nested media_data
        else if (resultMessage.media_data?.type &&
                 ["image", "video"].includes(resultMessage.media_data.type)) {
          mediaData = resultMessage.media_data;
        }
        
        if (mediaData && mediaData.path) {
          setExecutionMedia({
            path: mediaData.path,
            type: mediaData.type,
            alt: mediaData.alt,
            showControls: mediaData.showControls ?? true,
            autoPlay: mediaData.autoPlay ?? false,
            loop: mediaData.loop ?? false,
          });
          return; // Found media, stop searching
        }
      }
    }
  }, [flowPool, data.id]);

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMediaUrl(e.target.value);
  };

  // Auto-detect media type from URL
  const detectMediaType = (url: string): "image" | "video" => {
    const imageExts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'];
    const videoExts = ['.mp4', '.avi', '.mov', '.wmv', '.webm', '.mkv'];
    
    const cleanUrl = url.split('?')[0].toLowerCase();
    
    if (imageExts.some(ext => cleanUrl.endsWith(ext))) {
      return "image";
    }
    if (videoExts.some(ext => cleanUrl.endsWith(ext))) {
      return "video";
    }
    
    // Default to image
    return "image";
  };

  const mediaType = mediaUrl ? detectMediaType(mediaUrl) : "image";

  return (
    <>
      <NodeResizer
        minWidth={MIN_WIDTH}
        minHeight={MIN_HEIGHT}
        maxWidth={MAX_WIDTH}
        maxHeight={MAX_HEIGHT}
        onResize={(_, params) => {
          const { width, height } = params;
          debouncedResize(width, height);
        }}
        isVisible={selected}
        lineClassName="!border !border-primary"
        onResizeStart={() => {
          setIsResizing(true);
        }}
        onResizeEnd={() => {
          setIsResizing(false);
          debouncedResize.flush();
        }}
      />
      <div
        data-testid="media_player_node"
        style={{
          minWidth: nodeDataWidth,
          minHeight: nodeDataHeight,
        }}
        ref={nodeDiv}
        className={cn(
          "relative flex h-full w-full flex-col gap-2 rounded-xl border bg-background p-3 shadow-md",
          !isResizing && "transition-transform duration-200 ease-in-out",
          selected && "ring-2 ring-primary",
        )}
      >
        {/* Header with URL input */}
        <div className="flex items-center gap-2 border-b pb-2">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="Enter image or video URL..."
              value={mediaUrl}
              onChange={handleUrlChange}
              className="w-full text-sm"
            />
          </div>
        </div>

        {/* Media display area */}
        <div className="flex-1 flex items-center justify-center overflow-hidden rounded-lg bg-muted/30">
          {executionMedia ? (
            <div className="w-full h-full flex flex-col">
              <div className="text-xs text-muted-foreground px-2 py-1 border-b bg-muted/50">
                Execution Result
              </div>
              <div className="flex-1 overflow-hidden">
                <MediaDisplay
                  path={executionMedia.path}
                  type={executionMedia.type}
                  alt={executionMedia.alt}
                  showControls={executionMedia.showControls}
                  autoPlay={executionMedia.autoPlay}
                  loop={executionMedia.loop}
                  className="w-full h-full"
                />
              </div>
            </div>
          ) : mediaUrl ? (
            <div className="w-full h-full flex flex-col">
              <div className="text-xs text-muted-foreground px-2 py-1 border-b bg-muted/50">
                Manual Input
              </div>
              <div className="flex-1 overflow-hidden">
                <MediaDisplay
                  path={mediaUrl}
                  type={mediaType}
                  showControls={true}
                  className="w-full h-full"
                />
              </div>
            </div>
          ) : (
            <div className="text-center text-muted-foreground p-4">
              <p className="text-sm">Enter a media URL above or run the workflow</p>
              <p className="text-xs mt-2">Supports images (jpg, png, gif) and videos (mp4, webm)</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default MediaPlayerNode;