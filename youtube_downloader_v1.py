import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import os
import yt_dlp as youtube_dlp
import traceback


class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Backup Tool")
        self.root.geometry("700x500")
        self.root.resizable(True, True)

        self.create_widgets()
        self.download_thread = None
        self.stop_event = threading.Event()

    def create_widgets(self):
        # URL Entry
        ttk.Label(self.root, text="YouTube URL:").pack(
            pady=(10, 0), padx=20, anchor="w"
        )
        self.url_entry = ttk.Entry(self.root, width=80)
        self.url_entry.pack(pady=(0, 10), padx=20, fill=tk.X)

        # Format Selection
        ttk.Label(self.root, text="Output Format:").pack(padx=20, anchor="w")
        self.format_var = tk.StringVar(value="best")
        formats = [
            ("Best Quality (Video+Audio)", "best"),
            ("MP4", "mp4"),
            ("WebM", "webm"),
            ("Audio Only (MP3)", "mp3"),
        ]
        for text, value in formats:
            ttk.Radiobutton(
                self.root, text=text, variable=self.format_var, value=value
            ).pack(padx=20, anchor="w")

        # Subtitle Options
        ttk.Label(self.root, text="Subtitles:").pack(padx=20, anchor="w")
        self.subs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self.root, text="Embed Subtitles (if available)", variable=self.subs_var
        ).pack(padx=20, anchor="w")

        # Output Directory
        ttk.Label(self.root, text="Save Location:").pack(
            pady=(10, 0), padx=20, anchor="w"
        )
        dir_frame = ttk.Frame(self.root)
        dir_frame.pack(padx=20, fill=tk.X)

        self.dir_entry = ttk.Entry(dir_frame)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.dir_entry.insert(0, os.getcwd())

        ttk.Button(dir_frame, text="Browse", command=self.select_directory).pack(
            side=tk.RIGHT, padx=(5, 0)
        )

        # Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10, fill=tk.X, padx=20)

        ttk.Button(btn_frame, text="Start Download", command=self.start_download).pack(
            side=tk.LEFT, padx=(0, 10)
        )

        ttk.Button(btn_frame, text="Stop Download", command=self.stop_download).pack(
            side=tk.LEFT
        )

        # Log Output
        ttk.Label(self.root, text="Download Log:").pack(padx=20, anchor="w")
        self.log_area = scrolledtext.ScrolledText(
            self.root, state="disabled", height=15
        )
        self.log_area.pack(padx=20, pady=(0, 10), fill=tk.BOTH, expand=True)

    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)

    def log_message(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state="disabled")

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return

        save_path = self.dir_entry.get().strip()
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except:
                messagebox.showerror("Error", "Invalid save directory")
                return

        if self.download_thread and self.download_thread.is_alive():
            messagebox.showwarning("Warning", "Download already in progress")
            return

        self.stop_event.clear()
        self.log_message("=" * 50)
        self.log_message(f"Starting download: {url}")

        self.download_thread = threading.Thread(
            target=self.run_download, args=(url, save_path), daemon=True
        )
        self.download_thread.start()

    def stop_download(self):
        if self.download_thread and self.download_thread.is_alive():
            self.stop_event.set()
            self.log_message("Download cancellation requested...")

    def run_download(self, url, save_path):
        try:
            # Create basic options for info extraction
            info_opts = {
                "quiet": True,
                "no_warnings": False,
                "simulate": True,
                "skip_download": True,
                "logger": self.create_logger(),
            }

            # Extract info to determine content type
            with youtube_dlp.YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # Determine appropriate folder structure
            if "_type" in info and info["_type"] == "playlist":
                # Playlist - create folder with playlist name
                folder_name = info.get("title", "Playlist")
                final_path = os.path.join(
                    save_path, self.sanitize_filename(folder_name)
                )
                self.log_message(f"Downloading playlist to: {final_path}")
            elif (
                "channel" in info.get("extractor_key", "").lower()
                or "user" in info.get("extractor_key", "").lower()
            ):
                # Channel - create folder with channel name
                channel_name = info.get("uploader", info.get("channel", "Channel"))
                final_path = os.path.join(
                    save_path, self.sanitize_filename(channel_name)
                )
                self.log_message(f"Downloading channel content to: {final_path}")
            elif "entries" in info:
                # Playlist with entries but no playlist type
                folder_name = info.get("title", "Playlist")
                final_path = os.path.join(
                    save_path, self.sanitize_filename(folder_name)
                )
                self.log_message(f"Downloading playlist to: {final_path}")
            else:
                # Single video
                channel_name = info.get("uploader", info.get("channel", "Channel"))
                final_path = os.path.join(
                    save_path, self.sanitize_filename(channel_name)
                )
                self.log_message(f"Downloading video to: {final_path}")

            # Ensure the final path exists
            if not os.path.exists(final_path):
                os.makedirs(final_path)

            # Configure download options
            format_choice = self.format_var.get()

            # Base options
            ydl_opts = {
                "outtmpl": os.path.join(final_path, "%(title)s.%(ext)s"),
                "progress_hooks": [self.progress_hook],
                "ignoreerrors": True,
                "writethumbnail": True,
                "writedate": True,  # Preserve upload date
                "logger": self.create_logger(),
                "quiet": True,
                "no_warnings": False,
                # Remove all extra files
                "writedescription": False,
                "writeinfojson": False,
                "writeannotations": False,
                "writesubtitles": False,  # We'll handle subtitles differently
                "writeautomaticsub": False,
            }

            # Add subtitle options if enabled
            if self.subs_var.get() and format_choice != "mp3":
                # This will embed subtitles directly without creating separate files
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegEmbedSubtitle",
                    }
                ]
                ydl_opts["subtitleslangs"] = ["en.*", "a.en.*"]  # All English subtitles
                ydl_opts["writesubtitles"] = True  # Required for embedding
                ydl_opts["embed-subs"] = True  # Embed into video file

            # Set format based on selection
            if format_choice == "best":
                ydl_opts["format"] = "bestvideo+bestaudio/best"
            elif format_choice == "mp3":
                ydl_opts["format"] = "bestaudio"
                ydl_opts["postprocessors"] = ydl_opts.get("postprocessors", []) + [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }
                ]
            else:
                ydl_opts["format"] = f"best[ext={format_choice}]"

            # Add thumbnail embedding for all formats
            if format_choice != "mp3":
                # Only embed thumbnails for video formats
                ydl_opts["postprocessors"] = ydl_opts.get("postprocessors", []) + [
                    {
                        "key": "EmbedThumbnail",
                        "already_have_thumbnail": False,
                    }
                ]

            # Now perform the actual download
            with youtube_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not self.stop_event.is_set():
                self.log_message("All downloads completed!")
        except Exception as e:
            self.log_message(f"Fatal error: {str(e)}")
            self.log_message(traceback.format_exc())

    def sanitize_filename(self, name):
        """Remove invalid characters from filenames"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "")
        return name.strip()

    def create_logger(self):
        class YTDLLogger:
            def __init__(self, app):
                self.app = app

            def debug(self, msg):
                if not msg.startswith("[debug]"):
                    self.info(msg)

            def info(self, msg):
                self.app.root.after(0, self.app.log_message, msg.strip())

            def warning(self, msg):
                self.info(f"WARNING: {msg}")

            def error(self, msg):
                self.info(f"ERROR: {msg}")

        return YTDLLogger(self)

    def progress_hook(self, d):
        if self.stop_event.is_set():
            raise Exception("Download cancelled by user")

        if d["status"] == "downloading":
            percent = d.get("_percent_str", "N/A")
            speed = d.get("_speed_str", "N/A")
            eta = d.get("_eta_str", "N/A")
            message = f"Downloading: {percent} at {speed} | ETA: {eta}"
            self.log_message(message)
        elif d["status"] == "finished":
            self.log_message("Processing and embedding metadata...")


# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()
