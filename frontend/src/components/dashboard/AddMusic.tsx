import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Youtube, 
  Upload, 
  Link, 
  Loader2, 
  Plus,
  ChevronDown,
  ChevronUp,
  Music
} from 'lucide-react';
import { useToast } from '@/contexts/ToastContext';
import { Button, Card, Input } from '@/components/ui';
import { musicApi } from '@/lib/api';

export function AddMusic() {
  const { addToast } = useToast();
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<'youtube' | 'upload'>('youtube');
  
  // YouTube state
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [isAddingYoutube, setIsAddingYoutube] = useState(false);
  
  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleYoutubeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!youtubeUrl.trim()) return;

    setIsAddingYoutube(true);
    try {
      await musicApi.addFromYoutube(youtubeUrl);
      addToast('success', 'Đang tải nhạc từ YouTube...');
      setYoutubeUrl('');
    } catch (error: any) {
      console.error('Failed to add from YouTube:', error);
      addToast('error', error.response?.data?.error || 'Không thể tải nhạc');
    } finally {
      setIsAddingYoutube(false);
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      await musicApi.uploadFile(formData);
      addToast('success', 'Đã tải file lên thành công');
      setSelectedFile(null);
    } catch (error: any) {
      console.error('Failed to upload file:', error);
      addToast('error', error.response?.data?.error || 'Không thể tải file lên');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center">
            <Plus className="w-5 h-5 text-green-500" />
          </div>
          <div className="text-left">
            <h2 className="font-semibold">Thêm nhạc</h2>
            <p className="text-sm text-muted-foreground">
              YouTube hoặc tải file
            </p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-4">
              {/* Tabs */}
              <div className="flex gap-1 p-1 bg-muted rounded-lg">
                <button
                  onClick={() => setActiveTab('youtube')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-all ${
                    activeTab === 'youtube'
                      ? 'bg-background shadow-sm text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Youtube className="w-4 h-4" />
                  YouTube
                </button>
                <button
                  onClick={() => setActiveTab('upload')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-all ${
                    activeTab === 'upload'
                      ? 'bg-background shadow-sm text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Upload className="w-4 h-4" />
                  Tải file
                </button>
              </div>

              {/* YouTube Form */}
              <AnimatePresence mode="wait">
                {activeTab === 'youtube' && (
                  <motion.form
                    key="youtube"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 10 }}
                    onSubmit={handleYoutubeSubmit}
                    className="space-y-3"
                  >
                    <div className="relative">
                      <Link className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        type="url"
                        value={youtubeUrl}
                        onChange={(e) => setYoutubeUrl(e.target.value)}
                        placeholder="Dán link YouTube hoặc playlist..."
                        className="pl-10"
                        required
                      />
                    </div>
                    <Button
                      type="submit"
                      className="w-full"
                      disabled={isAddingYoutube || !youtubeUrl.trim()}
                    >
                      {isAddingYoutube ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Đang xử lý...
                        </>
                      ) : (
                        <>
                          <Youtube className="w-4 h-4 mr-2" />
                          Tải từ YouTube
                        </>
                      )}
                    </Button>
                    <p className="text-xs text-muted-foreground text-center">
                      Hỗ trợ video đơn lẻ và playlist
                    </p>
                  </motion.form>
                )}

                {activeTab === 'upload' && (
                  <motion.form
                    key="upload"
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    onSubmit={handleFileUpload}
                    className="space-y-3"
                  >
                    <label
                      htmlFor="file-upload"
                      className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
                        selectedFile
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:border-primary/50 hover:bg-muted/50'
                      }`}
                    >
                      {selectedFile ? (
                        <>
                          <Music className="w-8 h-8 text-primary mb-2" />
                          <p className="font-medium text-sm truncate max-w-full">
                            {selectedFile.name}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </>
                      ) : (
                        <>
                          <Upload className="w-8 h-8 text-muted-foreground mb-2" />
                          <p className="text-sm text-muted-foreground">
                            Click để chọn file nhạc
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            MP3, WAV, FLAC, OGG
                          </p>
                        </>
                      )}
                      <input
                        id="file-upload"
                        type="file"
                        accept=".mp3,.wav,.flac,.ogg,audio/*"
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </label>
                    
                    <Button
                      type="submit"
                      className="w-full"
                      disabled={isUploading || !selectedFile}
                    >
                      {isUploading ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Đang tải lên...
                        </>
                      ) : (
                        <>
                          <Upload className="w-4 h-4 mr-2" />
                          Tải file lên
                        </>
                      )}
                    </Button>
                  </motion.form>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
