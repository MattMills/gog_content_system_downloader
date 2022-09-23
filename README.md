# GOG repo downloader

This simple python script allows you to do bulk download/archive of (licensed) GOG repos, using historical build data from gogdb, or your own backup. It may be possible to pull old build info from the local galaxy SQLite database as well.

## Steps

1. Git clone the repo
2. Identify build manifests and place them in a build_manifests subdirectory
3. Place a product.json file containing the relevant build data in gogdb's format
4. Auth (see auth section below) and place your acquired bearer token into gog_token.json
5. Update the download_dir and allowed_products in gog_content_system_downloader.py
6. Run gog_content_system_downloader.py 

## Auth
1. Open a web browser and a console
2. In the console prep the token command (needs to be acquired somewhat quickly)
```
curl -v 'https://auth.gog.com/token?client_id=46899977096215655&redirect_uri=https%3A%2F%2Fembed.gog.com%2Fon_login_success%3Forigin%3Dclient&client_secret=9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9&grant_type=authorization_code&code='
```

3. In the webbrowser go to link below, login, then copy the "code" parameter in the URL you are redirected to into the end of the curl command above, and send the token request.
```
https://auth.gog.com/auth?client_id=46899977096215655&client_secret=9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9&layout=client2&response_type=code&&redirect_uri=https%3A%2F%2Fembed.gog.com%2Fon_login_success%3Forigin%3Dclient
```
4. Place received JSON response into auth_token.json
5. Further token renewal should happen automatically.
