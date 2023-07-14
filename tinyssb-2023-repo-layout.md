# tinySSB repo layout

Why a "giant tinySSB repo", how to structure it?

One giant repo helps with a few pain points.  It allows us to pin down
requirements and make on boarding one download, etc.

Some rules are mecessary: it shouldn't include proprietary code that
could damage the project, and we must give appropriate attributions.
I.e. all import have MIT license.


## Directory Layout

```
tinySSB-2023/                   // YYYY as the top level version
 + DOC/
   + architecture.md            // intro to SSB and tSSB arch, terminology
   + bipf.md                    / /serialization, for repl protocols and apps
   + packet-format.md           // byte-level
   + well-known-DMX-values.md   // table, "network" constants if appropriate
   + replication/               // embrace improvements over time
     + WANT-CHNK-2023.md        // packet format and timing (from LoRa to ws)
   + apps/
     + ABT.md                   // about app
     + BOX.md                   // SSB.classic encrypted body
     + che.md                   // a chess game
     + cH7.md                   // another chess game
     + KAN.md                   // Kanban board
     + TAV.md                   // Text-and-Voice chat app
     + Txt.md                   // shared text document app
     README.md                  // how-to for describing tinySSB apps
   + storage                    // documenting various storing techniques
     + hashy.md                 // all chunks in a hash-named tree
     + side_chainy.md           // each sidechain as an independent file
     + logy.md                  // one inflated log, plus one frontier file
     README.md
   README.md                    // doc guide (where to find what, also ext links)
 + android/
   + vossbol                    // flagship tinySSB app for Android
   + ...                        // e.g. without codec2
   + virtual_backend            // developing GUI+appLogic in a Chrome browser
   README.md                    // annotated directory
 + esp32/
   +lora-2023/                  // heltec 32_V2, tBeam V1.1,
   +t-deck/                     // lilygo T-deck
 + rpi_nano_w/
   ...
 + python/
   + tav_chat
   + pkt_dump
   + simple_pub
 LICENSE                        // MIT
 README.md
```


## Open Issues

- add text here


## Closed Issues

- add text here


----
