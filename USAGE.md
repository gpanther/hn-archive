# Usage

There is *no need* to deploy an other instance of this application. The current code is deployed at [hn-archive.appspot.com](https://hn-archive.appspot.com/). You can also find there a link with to the file containing the first 10m comments from [Hacker News](https://news.ycombinator.com/). I'm also working with the [Archive Team](http://archiveteam.org/) to provide a continuously update version. If you still have questions, [contact me](mailto:dify.ltd@gmail.com).

## Google App Engine part

You can find this in the `gae` folder.

## Extracting the data from Google AppEngine

* Deploy a version with `ENABLE_DATASTORE_WRITES` set to `False`
* Wait until the current tasks stop (and/or force delete them from the developer console)
* Disable datastore writes from the developer console (for maximum safety) and export the data to a Google Cloud Storage bucket
* Enable datastore writes and use the Data Store Admin to delete all entities of type `HNEntry` and `InaccessibleHNEntry`
* Deploy a version with `ENABLE_DATASTORE_WRITES` set to `True` to continue fetching the data
* Extract the data from Cloud Storage using gsutil: `gsutil -m rsync -r gs://[bucket name] [output directory]/`
* Delete the data from Cloud Storage

Post-processing the downloaded data:

* Convert the entities into JSON:  
`python extract_data/01_record_to_json.py [backup directory]/ 2> 01_record.log | bzip2 -9 > hn_comments_1.json.bz2`
* Find the comments missing from the above file:  
`bzcat hn_comments_1.json.bz2 | python extract_data/02_find_missing_ids.py 1 9948139 > 02_missing.log`  
(1 and 9948139 are the min/max ID from the dataset - anything outside those won't be considered "missing")
* Fetch the missing comments from [Algolia](https://hn.algolia.com/api) or the main site:
`python extract_data/03_fetch_missing.py | bzip2 -9 > hn_comments_missing_1.json.bz2`  
(you need to add your login cookie to `03_fetch_missing.py` and make sure that you have "showdead" set to "yes" to ensure that you can retrieve all comments)
* Sort all the comments:
`bzcat *.bz2 | pv | python extract_data/04_prefix_with_index.py | sort -g | python extract_data/04_remove_prefix.py | bzip2 -9 > comments_sorted.json.bz2`

The final file will contain comments sorted by their ID, with one comment/story per line, encoded in JSON.

