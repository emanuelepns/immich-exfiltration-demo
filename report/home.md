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
- **Victim instance**: hosts Immich app.
- **Attacker instance**: hosts the malicious script and catches the exfiltrated api key.

Both were set up with a [minimal version](https://wiki.ubuntu.com/Minimal) of Ubuntu 24.04.4 LTS.
For the domains, I decided to use a dedicated subdomain under my personal domain for the victim machine, and a free domain obtained via [FreeDNS](https://freedns.afraid.org/) for the attacker.

To ensure a production-like setup, I installed [Caddy](https://caddyserver.com/) as a reverse proxy on both machines as it manages the SSL certificates automatically with just a two line configuration. This step was crucial because unencrypted HTTP traffic is often rejected or restricted, making a valid HTTPS setup necessary for the exploit chain to succeed seamlessly.
### Immich setup

