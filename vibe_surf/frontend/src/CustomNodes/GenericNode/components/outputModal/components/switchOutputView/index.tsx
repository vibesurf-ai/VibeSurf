import { useMemo } from "react";
import JsonOutputViewComponent from "@/components/core/jsonOutputComponent/json-output-view";
import { MAX_TEXT_LENGTH } from "@/constants/constants";
import type { LogsLogType, OutputLogType } from "@/types/api";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import DataOutputComponent from "../../../../../../components/core/dataOutputComponent";
import { MediaDisplay } from "../../../../../../components/MediaDisplay";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../../../../components/ui/alert";
import { Case } from "../../../../../../shared/components/caseComponent";
import TextOutputView from "../../../../../../shared/components/textOutputView";
import useFlowStore from "../../../../../../stores/flowStore";
import ErrorOutput from "./components";

// Define the props type
interface SwitchOutputViewProps {
  nodeId: string;
  outputName: string;
  type: "Outputs" | "Logs";
}

const SwitchOutputView: React.FC<SwitchOutputViewProps> = ({
  nodeId,
  outputName,
  type,
}) => {
  const flowPool = useFlowStore((state) => state.flowPool);

  const flowPoolNode = (flowPool[nodeId] ?? [])[
    (flowPool[nodeId]?.length ?? 1) - 1
  ];

  const results: OutputLogType | LogsLogType =
    (type === "Outputs"
      ? flowPoolNode?.data?.outputs?.[outputName]
      : flowPoolNode?.data?.logs?.[outputName]) ?? {};
  const resultType = results?.type;
  let resultMessage = results?.message ?? {};
  const RECORD_TYPES = ["array", "message"];
  const JSON_TYPES = ["data", "object"];
  if (resultMessage?.raw) {
    resultMessage = resultMessage.raw;
  }

  // Debug logging - Always log when component renders
  console.log("[SwitchOutputView] Rendering for nodeId:", nodeId, "outputName:", outputName);
  console.log("[SwitchOutputView] resultType:", resultType);
  console.log("[SwitchOutputView] resultMessage:", resultMessage);
  console.log("[SwitchOutputView] resultMessage keys:", Object.keys(resultMessage || {}));
  
  // Debug logging for media viewer - check all possible structures
  console.log("[MediaViewer Debug] Checking for media content");
  console.log("[MediaViewer Debug] resultMessage.data:", resultMessage?.data);
  console.log("[MediaViewer Debug] resultMessage.type:", resultMessage?.type);
  console.log("[MediaViewer Debug] resultMessage.path:", resultMessage?.path);
  console.log("[MediaViewer Debug] resultMessage.media_data:", resultMessage?.media_data);
  
  if (resultMessage?.data?.type === "image" || resultMessage?.data?.type === "video") {
    console.log("[MediaViewer Debug] ✅ MEDIA DETECTED in data! Type:", resultMessage.data.type);
    console.log("[MediaViewer Debug] Path:", resultMessage.data.path);
  }
  if (resultMessage?.type === "image" || resultMessage?.type === "video") {
    console.log("[MediaViewer Debug] ✅ MEDIA DETECTED directly! Type:", resultMessage.type);
    console.log("[MediaViewer Debug] Path:", resultMessage.path);
  }
  if (resultMessage?.media_data?.type === "image" || resultMessage?.media_data?.type === "video") {
    console.log("[MediaViewer Debug] ✅ MEDIA DETECTED in media_data! Type:", resultMessage.media_data.type);
    console.log("[MediaViewer Debug] Path:", resultMessage.media_data.path);
  }

  const resultMessageMemoized = useMemo(() => {
    if (!resultMessage) return "";

    if (
      typeof resultMessage === "string" &&
      resultMessage.length > MAX_TEXT_LENGTH
    ) {
      return `${resultMessage.substring(0, MAX_TEXT_LENGTH)}...`;
    }
    if (Array.isArray(resultMessage)) {
      return resultMessage.map((item) => {
        if (item?.data && typeof item?.data === "object") {
          const truncatedData = Object.fromEntries(
            Object.entries(item?.data).map(([key, value]) => {
              if (typeof value === "string" && value.length > MAX_TEXT_LENGTH) {
                return [key, `${value.substring(0, MAX_TEXT_LENGTH)}...`];
              }
              return [key, value];
            }),
          );
          return { ...item, data: truncatedData };
        }
        return item;
      });
    }

    return resultMessage;
  }, [resultMessage]);

  // Robust media detection
  const isMedia = useMemo(() => {
    try {
      // Case 1: Message type with data.type
      if (resultType === "message" &&
          resultMessageMemoized?.data?.type &&
          ["image", "video"].includes(resultMessageMemoized.data.type)) {
        return true;
      }
      
      // Case 2: Object type (Data) with direct type property
      // This matches the structure seen in logs: {path: "...", type: "image", ...}
      if (resultType === "object" &&
          resultMessageMemoized &&
          typeof resultMessageMemoized === "object") {
            
        // Direct property check
        if (["image", "video"].includes(resultMessageMemoized.type)) {
          return true;
        }
        
        // Nested media_data check
        if (resultMessageMemoized.media_data &&
            ["image", "video"].includes(resultMessageMemoized.media_data.type)) {
          return true;
        }
      }
      
      return false;
    } catch (e) {
      console.error("Error in isMedia check:", e);
      return false;
    }
  }, [resultType, resultMessageMemoized]);

  return type === "Outputs" ? (
    <>
      <Case condition={!resultType || resultType === "unknown"}>
        <div>NO OUTPUT</div>
      </Case>
      <Case condition={resultType === "error" || resultType === "ValueError"}>
        <ErrorOutput
          value={`${resultMessageMemoized?.errorMessage}\n\n${resultMessageMemoized?.stackTrace}`}
        />
      </Case>

      <Case condition={resultType === "text"}>
        <TextOutputView left={false} value={resultMessageMemoized} />
      </Case>

      {/* Check for media content BEFORE checking RECORD_TYPES */}
      <Case condition={isMedia}>
        <div className="p-4">
          {resultMessageMemoized?.data?.path ? (
            <MediaDisplay
              path={resultMessageMemoized.data.path}
              type={resultMessageMemoized.data.type}
              alt={resultMessageMemoized.data.alt}
              showControls={resultMessageMemoized.data.showControls ?? true}
              autoPlay={resultMessageMemoized.data.autoPlay ?? false}
              loop={resultMessageMemoized.data.loop ?? false}
            />
          ) : resultMessageMemoized?.media_data?.path ? (
            <MediaDisplay
              path={resultMessageMemoized.media_data.path}
              type={resultMessageMemoized.media_data.type}
              alt={resultMessageMemoized.media_data.alt}
              showControls={resultMessageMemoized.media_data.showControls ?? true}
              autoPlay={resultMessageMemoized.media_data.autoPlay ?? false}
              loop={resultMessageMemoized.media_data.loop ?? false}
            />
          ) : resultMessageMemoized?.path ? (
            <MediaDisplay
              path={resultMessageMemoized.path}
              type={resultMessageMemoized.type}
              alt={resultMessageMemoized.alt}
              showControls={resultMessageMemoized.showControls ?? true}
              autoPlay={resultMessageMemoized.autoPlay ?? false}
              loop={resultMessageMemoized.loop ?? false}
            />
          ) : (
            <div className="text-muted-foreground">Invalid media data</div>
          )}
        </div>
      </Case>

      <Case condition={RECORD_TYPES.includes(resultType) && !isMedia}>
        <DataOutputComponent
          rows={
            Array.isArray(resultMessageMemoized)
              ? (resultMessageMemoized as Array<any>).every(
                  (item) => item?.data,
                )
                ? (resultMessageMemoized as Array<any>).map(
                    (item) => item?.data,
                  )
                : resultMessageMemoized
              : Object.keys(resultMessageMemoized)?.length > 0
                ? [resultMessageMemoized]
                : []
          }
          pagination={true}
          columnMode="union"
        />
      </Case>
      <Case condition={JSON_TYPES.includes(resultType) && !isMedia}>
        <JsonOutputViewComponent
          nodeId={nodeId}
          outputName={outputName}
          data={resultMessageMemoized}
        />
      </Case>

      <Case condition={resultType === "stream"}>
        <div className="flex h-full w-full items-center justify-center align-middle">
          <Alert variant={"default"} className="w-fit">
            <ForwardedIconComponent
              name="AlertCircle"
              className="h-5 w-5 text-primary"
            />
            <AlertTitle>{"Streaming is not supported"}</AlertTitle>
            <AlertDescription>
              {
                "Use the playground to interact with components that stream data"
              }
            </AlertDescription>
          </Alert>
        </div>
      </Case>
    </>
  ) : (
    <DataOutputComponent
      rows={
        Array.isArray(results)
          ? (results as Array<any>).every((item) => item?.data)
            ? (results as Array<any>).map((item) => item?.data)
            : results
          : Object.keys(results)?.length > 0
            ? [results]
            : []
      }
      pagination={true}
      columnMode="union"
    />
  );
};

export default SwitchOutputView;
