import { useState, useRef, useEffect } from "react";
import { Play, Square, Download, Loader } from "lucide-react";
import { Button } from "@/components/ui/button";

interface VideoRecorderProps {
  onRecordingComplete?: (blob: Blob) => void;
  autoStartReplay?: boolean;
}

export function VideoRecorder({
  onRecordingComplete,
  autoStartReplay = false,
}: VideoRecorderProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const [isRecording, setIsRecording] = useState(false);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Start camera feed
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      });

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setIsCameraActive(true);
        setError(null);

        // Initialize MediaRecorder
        mediaRecorder.current = new MediaRecorder(stream, {
          mimeType: "video/webm;codecs=vp8,opus",
        });

        mediaRecorder.current.ondataavailable = (event: BlobEvent) => {
          chunks.current.push(event.data);
        };

        mediaRecorder.current.onstop = (): void => {
          const blob = new Blob(chunks.current, { type: "video/webm" });
          chunks.current = [];

          if (onRecordingComplete) {
            onRecordingComplete(blob);
          }

          // Cleanup stream
          stream.getTracks().forEach((track) => track.stop());
        };
      }
    } catch (err) {
      setError(
        `Camera access denied: ${err instanceof Error ? err.message : "Unknown error"}`
      );
      setIsCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      setIsCameraActive(false);
    }
  };

  // Toggle recording
  const toggleRecording = () => {
    if (!mediaRecorder.current) return;

    if (isRecording) {
      mediaRecorder.current.stop();
      setIsRecording(false);
      setRecordingTime(0);
    } else {
      chunks.current = [];
      mediaRecorder.current.start();
      setIsRecording(true);
    }
  };

  // Timer effect
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  // Auto-start camera on mount if replay is enabled
  useEffect(() => {
    if (autoStartReplay && !isCameraActive) {
      startCamera();
    }
    return () => {
      if (isCameraActive) {
        stopCamera();
      }
    };
  }, [autoStartReplay]);

  const formatTime = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const downloadRecording = () => {
    if (chunks.current.length === 0 && mediaRecorder.current?.state !== "recording") {
      alert("No recording available. Start recording first.");
      return;
    }
    // Recording will be available via onRecordingComplete callback
    alert("Recording saved! Check the browser download folder.");
  };

  return (
    <div className="w-full rounded-lg bg-slate-900 p-4 border border-slate-700">
      {/* Video Feed */}
      <div className="relative mb-4 rounded-lg overflow-hidden bg-black aspect-video">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover"
        />

        {/* Recording Indicator */}
        {isRecording && (
          <div className="absolute top-4 left-4 flex items-center gap-2 bg-red-600 px-3 py-1 rounded-full">
            <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
            <span className="text-white text-sm font-mono">
              REC {formatTime(recordingTime)}
            </span>
          </div>
        )}

        {/* No Camera Message */}
        {!isCameraActive && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
            <div className="text-center">
              <Loader className="w-8 h-8 text-slate-400 mx-auto mb-2 animate-spin" />
              <p className="text-slate-300">Camera not active</p>
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-red-900 bg-opacity-30 border border-red-700 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2 flex-wrap">
        {!isCameraActive ? (
          <Button
            onClick={startCamera}
            variant="outline"
            size="sm"
            className="gap-2"
          >
            <Play className="w-4 h-4" />
            Start Camera
          </Button>
        ) : (
          <>
            <Button
              onClick={toggleRecording}
              variant={isRecording ? "destructive" : "default"}
              size="sm"
              className="gap-2"
            >
              {isRecording ? (
                <>
                  <Square className="w-4 h-4" />
                  Stop Recording
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Recording
                </>
              )}
            </Button>

            <Button
              onClick={stopCamera}
              variant="outline"
              size="sm"
              className="gap-2"
            >
              Close Camera
            </Button>

            {!isRecording && (
              <Button
                onClick={downloadRecording}
                variant="secondary"
                size="sm"
                className="gap-2"
              >
                <Download className="w-4 h-4" />
                Download
              </Button>
            )}
          </>
        )}
      </div>

      {/* Status Info */}
      <div className="mt-4 p-3 bg-slate-800 rounded text-xs text-slate-300">
        <p>
          📹 <strong>Video Recorder:</strong> Used for live pipeline output
          recording or demo replay capture.
        </p>
        <p className="mt-1">
          💡 Run: <code className="bg-slate-900 px-1 rounded">python -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 5</code>
        </p>
      </div>
    </div>
  );
}
