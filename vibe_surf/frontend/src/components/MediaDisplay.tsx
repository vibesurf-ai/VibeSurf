import { useState, useRef } from "react";
import { Download, Maximize2, X, Play, Pause, Volume2, VolumeX, ZoomIn, ZoomOut, RotateCw } from "lucide-react";
import { BASE_URL_API } from "../constants/constants";

interface MediaDisplayProps {
  path: string;
  type: "image" | "video";
  alt?: string;
  className?: string;
  showControls?: boolean;
  autoPlay?: boolean;
  loop?: boolean;
}

export const MediaDisplay = ({ 
  path, 
  type, 
  alt, 
  className = "",
  showControls = true,
  autoPlay = false,
  loop = false
}: MediaDisplayProps) => {
  const [isZoomed, setIsZoomed] = useState(false);
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(0.8);
  const [imageZoom, setImageZoom] = useState(1);
  const [imageRotation, setImageRotation] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  
  // Construct the full URL
  // If path is already a full URL (http/https), use it directly
  // Otherwise, treat it as a local file path
  const mediaSrc = path.startsWith("http://") || path.startsWith("https://")
    ? path
    : path;  // For local files, use path directly (browser file:// protocol or relative path)

  const handleDownload = async () => {
    try {
      const response = await fetch(mediaSrc);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Get filename from path, or try to extract from Content-Disposition header if available
      // but don't rely on response.headers access directly causing undefined error
      let filename = path.split('/').pop() || 'download';
      
      // Safely try to get filename from headers if possible, but fallback gracefully
      try {
        if (response.headers) {
          const contentDisposition = response.headers.get('Content-Disposition');
          if (contentDisposition) {
            const matches = /filename="?([^"]+)"?/.exec(contentDisposition);
            if (matches && matches[1]) {
              filename = matches[1];
            }
          }
        }
      } catch (e) {
        // Ignore header parsing errors
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
      // Fallback download method for simple links
      const a = document.createElement('a');
      a.href = mediaSrc;
      a.download = path.split('/').pop() || 'download';
      a.target = "_blank";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  const handleFullscreen = () => {
    setIsZoomed(!isZoomed);
  };

  const handleZoomIn = () => {
    setImageZoom(prev => Math.min(prev + 0.2, 3));
  };

  const handleZoomOut = () => {
    setImageZoom(prev => Math.max(prev - 0.2, 0.5));
  };

  const handleRotate = () => {
    setImageRotation(prev => (prev + 90) % 360);
  };

  const resetImageTransform = () => {
    setImageZoom(1);
    setImageRotation(0);
  };

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
    }
  };

  if (type === "image") {
    return (
      <>
        <div className={`relative group overflow-hidden rounded-lg border border-border bg-muted ${className}`}>
          <img 
            src={mediaSrc} 
            alt={alt || "Generated image"} 
            className="w-full h-auto object-cover cursor-pointer transition-transform hover:scale-105"
            loading="lazy"
            onClick={handleFullscreen}
          />
          
          {showControls && (
            <div className="absolute bottom-2 right-2 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleFullscreen}
                className="p-2 rounded-md bg-black/70 text-white hover:bg-black/90 transition-colors"
                title="Fullscreen"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
              <button
                onClick={handleDownload}
                className="p-2 rounded-md bg-black/70 text-white hover:bg-black/90 transition-colors"
                title="Download"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Fullscreen Modal */}
        {isZoomed && (
          <div 
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget) handleFullscreen();
            }}
          >
            <div className="relative max-w-7xl max-h-screen w-full h-full flex flex-col">
              {/* Control Bar */}
              <div className="flex items-center justify-between p-4 bg-black/50 rounded-t-lg">
                <div className="flex gap-2">
                  <button 
                    className="p-2 text-white bg-white/10 rounded-md hover:bg-white/20 transition-colors"
                    onClick={handleZoomIn}
                    title="Zoom In"
                  >
                    <ZoomIn className="w-5 h-5" />
                  </button>
                  <button 
                    className="p-2 text-white bg-white/10 rounded-md hover:bg-white/20 transition-colors"
                    onClick={handleZoomOut}
                    title="Zoom Out"
                  >
                    <ZoomOut className="w-5 h-5" />
                  </button>
                  <button 
                    className="p-2 text-white bg-white/10 rounded-md hover:bg-white/20 transition-colors"
                    onClick={handleRotate}
                    title="Rotate"
                  >
                    <RotateCw className="w-5 h-5" />
                  </button>
                  <button 
                    className="px-3 py-2 text-white bg-white/10 rounded-md hover:bg-white/20 transition-colors text-sm"
                    onClick={resetImageTransform}
                    title="Reset"
                  >
                    Reset
                  </button>
                </div>
                <div className="flex gap-2">
                  <button 
                    className="p-2 text-white bg-white/10 rounded-md hover:bg-white/20 transition-colors"
                    onClick={handleDownload}
                    title="Download"
                  >
                    <Download className="w-5 h-5" />
                  </button>
                  <button 
                    className="p-2 text-white bg-white/10 rounded-md hover:bg-white/20 transition-colors"
                    onClick={handleFullscreen}
                    title="Close"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Image Display */}
              <div className="flex-1 flex items-center justify-center overflow-hidden">
                <img 
                  src={mediaSrc} 
                  alt={alt || "Zoomed image"} 
                  className="max-w-full max-h-full object-contain rounded-md transition-transform duration-200"
                  style={{
                    transform: `scale(${imageZoom}) rotate(${imageRotation}deg)`,
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  if (type === "video") {
    return (
      <>
        <div className={`relative group rounded-lg overflow-hidden border border-border bg-muted ${className}`}>
          <video
            ref={videoRef}
            src={mediaSrc}
            loop={loop}
            autoPlay={autoPlay}
            muted={isMuted}
            className="w-full h-auto"
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
          >
            Your browser does not support the video tag.
          </video>
          
          {showControls && (
            <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="flex items-center gap-2">
                <button
                  onClick={togglePlayPause}
                  className="p-2 rounded-md bg-white/20 text-white hover:bg-white/30 transition-colors"
                  title={isPlaying ? "Pause" : "Play"}
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>
                
                <button
                  onClick={toggleMute}
                  className="p-2 rounded-md bg-white/20 text-white hover:bg-white/30 transition-colors"
                  title={isMuted ? "Unmute" : "Mute"}
                >
                  {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                </button>

                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={volume}
                  onChange={handleVolumeChange}
                  className="w-20 h-1 bg-white/30 rounded-lg appearance-none cursor-pointer"
                  title="Volume"
                />

                <div className="flex-1" />
                
                <button
                  onClick={handleFullscreen}
                  className="p-2 rounded-md bg-white/20 text-white hover:bg-white/30 transition-colors"
                  title="Fullscreen"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
                
                <button
                  onClick={handleDownload}
                  className="p-2 rounded-md bg-white/20 text-white hover:bg-white/30 transition-colors"
                  title="Download"
                >
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Fullscreen Video Modal */}
        {isZoomed && (
          <div 
            className="fixed inset-0 z-50 flex items-center justify-center bg-black p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget) handleFullscreen();
            }}
          >
            <div className="relative w-full h-full max-w-7xl flex flex-col">
              <div className="flex justify-end p-4">
                <button 
                  className="p-2 text-white bg-white/10 rounded-md hover:bg-white/20 transition-colors"
                  onClick={handleFullscreen}
                  title="Close"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
              
              <div className="flex-1 flex items-center justify-center">
                <video
                  src={mediaSrc}
                  controls
                  loop={loop}
                  autoPlay={isPlaying}
                  className="max-w-full max-h-full"
                >
                  Your browser does not support the video tag.
                </video>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  return null;
};