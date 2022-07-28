Tools for scraping and analyzing Reddit and for messaging Redditors.

As of 2022-07-28 the help messages read:

```
usage: reddit-query.py [-h] [-a AFTER] [-b BEFORE] [-l LIMIT] [-c COMMENTS_NUM] [-r SUBREDDIT]
                       [--sample] [--skip] [-t] [-L] [-V] [--version]

Query Pushshift and Reddit APIs.

options:
  -h, --help            show this help message and exit
  -a AFTER, --after AFTER
                        submissions after: epoch, integer[s|m|h|d], or Y-m-d (pendulum). Using
                        it without before starts in 1970!
  -b BEFORE, --before BEFORE
                        submissions before: epoch, integer[s|m|h|d], or Y-m-d (pendulum).
  -l LIMIT, --limit LIMIT
                        limit to (default: 5) results
  -c COMMENTS_NUM, --comments_num COMMENTS_NUM
                        number of comments threshold '[<>]\d+]' (default: False). Note: this is
                        updated as Pushshift ingests, `score` is not.
  -r SUBREDDIT, --subreddit SUBREDDIT
                        subreddit to query (default: AmItheAsshole)
  --sample              sample complete date range up to limit, rather than first submissions
                        within limit
  --skip                skip all Reddit fetches; pushshift only
  -t, --throwaway-only  only throwaway accounts ('throw' and 'away') get fetched from Reddit
  -L, --log-to-file     log to file reddit-query.py.log
  -V, --verbose         increase logging verbosity (specify multiple times for more)
  --version             show program's version number and exit
```

```
usage: reddit-watch.py [-h] [-i INIT] [--hours HOURS] [-L] [-V] [--version]

Watch the deletion/removal status of Reddit messages. Initialize subreddits to
be watched first (e.g., 'Advice+AmItheAsshole). Schedule using cron or launchd

options:
  -h, --help            show this help message and exit
  -i INIT, --init INIT  INITIALIZE `+` delimited subreddits to watch
  --hours HOURS         previous HOURS to fetch
  -L, --log-to-file     log to file reddit-watch.py.log
  -V, --verbose         increase logging verbosity (specify multiple times for more)
  --version             show program's version number and exit
```

```
usage: reddit-message.py [-h] -i FILENAME [-a FILENAME] [-g FILENAME] 
                         [-d] [-e] [-p] [-t] [-r RATE_LIMIT] [-s] 
                         [-D] [-L] [-V] [--version]

Message Redditors using usernames in CSV files from reddit-query.py
or reddit-watch.py .

options:
  -h, --help            show this help message and exit
  -i FILENAME, --input-fn FILENAME
                        CSV filename, with usernames, created by reddit-query.py
  -a FILENAME, --archive-fn FILENAME
                        CSV filename of previously messaged users to skip; 
                        created if doesn't exist 
                        (default: reddit-message-users-past.csv)
  -g FILENAME, --greeting-fn FILENAME
                        greeting message filename (default: greeting.txt)
  -d, --only-deleted    select deleted users only
  -e, --only-existent   select existent (NOT deleted) users only
  -p, --only-pseudonym  select pseudonyms only (NOT throwaway)
  -t, --only-throwaway  select throwaway accounts only ('throw' and 'away')
  -r RATE_LIMIT, --rate-limit RATE_LIMIT
                        rate-limit in seconds between messages (default: 40)
  -s, --show-csv-users  also show all users from input CSV on terminal
  -D, --dry-run         list greeting and users but don't message
  -L, --log-to-file     log to file reddit-message.py.log
  -V, --verbose         increase logging verbosity (specify multiple 
                        times for more)
  --version             show program's version number and exit
```
