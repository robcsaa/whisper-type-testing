# Test Phrases
These phrases are for TESTING ONLY. They should NEVER be used for training the model.

**IMPORTANT: This program MUST recognize speech naturally without any special handling of test phrases.**
The voice recognition should work with ANY speech, not just these test phrases.

1. "check one two three four five"
2. "hello world"
3. "buffer overflow"

## Notes
- Uses PipeWire or ALC245 for audio input
- Audio processed at 16kHz
- Ctrl+Alt+V to start/stop
- Text appears at cursor position 
- Uses general speech recognition, not trained on specific phrases
- Only applies basic spell check, no test phrase matching

## Development Guidelines
- NEVER add code that specifically recognizes the test phrases
- NEVER force any recognition to match test phrases
- DO NOT add special rules for these test phrases
- Speech recognition MUST work for general text, not just these phrases
- Use standard spell checking only 

                                              x@arco
                   /-                       x@arco
                  ooo:                      ------
                 yoooo/                     OS: ArcoLinux x86_64
                yooooooo                    Host: Victus by HP Laptop 16-e0xxx
               yooooooooo                   Kernel: Linux 6.13.7-zen1-1-zen
              yooooooooooo                  Uptime: 12 hours, 51 mins
            .yooooooooooooo                 Packages: 1651 (pacman), 13 (flatpak)
           .oooooooooooooooo                Shell: zsh 5.9
          .oooooooarcoooooooo               Display (CMN1602): 1920x1080 @ 144 Hz in 16" ]
         .ooooooooo-oooooooooo              DE: KDE Plasma 6.3.3
        .ooooooooo-  oooooooooo             WM: KWin (Wayland)
       :ooooooooo.    :ooooooooo            WM Theme: Arc-Dark
      :ooooooooo.      :ooooooooo           Theme: oxygen (ArcDark) [Qt], Arc-Dark [GTK2/]
     :oooarcooo         .oooarcooo          Icons: Surfn-Plasma-Dark [Qt], Surfn-Plasma-D]
    :ooooooooy           .ooooooooo         Font: Noto Sans (10pt) [Qt], Noto Sans (10pt)]
   :ooooooooo   /ooooooooooooooooooo        Cursor: Breeze_Light (24px)
  :ooooooooo      .-ooooooooooooooooo.      Terminal: alacritty 0.15.1
  ooooooooo-            -ooooooooooooo.     Terminal Font: hack (11.0pt)
 ooooooooo-                .-oooooooooo.    CPU: AMD Ryzen 7 5800H (16) @ 4.46 GHz
ooooooooo.                    -ooooooooo    GPU 1: NVIDIA GeForce RTX 3060 Mobile / Max-Q]
                                            GPU 2: AMD Radeon Vega Series / Radeon Vega M]
                                            Memory:/ 14.96 GiB (58%)
                                            Swap: / 8.80 GiB (46%)
                                            Disk (/): / 455.00 GiB (20%) - btrfs
                                            Local IP (wlan0): 192.168.12.203/24
                                            Battery (Primary): 100% [AC Connected]
                                            Locale: en_US.UTF-8