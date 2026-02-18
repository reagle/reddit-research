Tools for scraping and analyzing Reddit and for messaging Redditors.

```
uv tool install https://github.com/reagle/reddit-research.git
```

Note that the following install is pinned to pendulum 2.1.2 ([pendulum 3 requires rust and cargo](https://pendulum.eustace.io/blog/announcing-pendulum-3-0-0.html)) because wheels are not provided for python 3.13.

## reddit-search

```
❯ reddit-search -h
usage: reddit-search [-h] [-r] [-c COLUMN] [-L] [-V] [--version] FILE

Facilitate a search of phrases appearing in a spreadsheet column
(default: 'phrase') by generating queries against search engines and
opening the results in browser tabs. Search engines include Google,
Reddit, and RedditSearch/Pushshift.

> reddit-search demo-phrases.csv -c phrase

If you wish to test the efficacy of a disguised/spun phrase, also
include a column of the spun phrase and the 'url' of the source. This
will automatically check the results for that URL.

> reddit-search demo-phrases.csv -c weakspins

positional arguments:
  FILE

options:
  -h, --help           show this help message and exit
  -r, --recheck        recheck non-NULL values in 'found' column
  -c, --column COLUMN  sheet column to query [default: 'phrase']
  -L, --log-to-file    log to file reddit-search.log
  -V, --verbose        increase verbosity from critical though error, warning, info, and debug
  --version            show program's version number and exit
```

## reddit-query

```
usage: reddit-query [-h] [-a AFTER] [-b BEFORE] [-l LIMIT] [-c COMMENTS_NUM]
                    [-r SUBREDDIT] [--sample] [--skip] [-t] [-L] [-V]
                    [--version]

Query Pushshift and Reddit APIs.

options:
  -h, --help            show this help message and exit
  -a, --after AFTER     submissions after: Y-m-d (any pendulum parsable).
                        Using it without before starts in 1970!
  -b, --before BEFORE   submissions before: Y-m-d (any pendulum parsable).
                        Using it without before starts in 1970!
  -l, --limit LIMIT     limit to (default: 5) results
  -c, --comments_num COMMENTS_NUM
                        number of comments threshold '[<>]\d+]' (default:
                        False). Note: this is updated as Pushshift ingests,
                        `score` is not.
  -r, --subreddit SUBREDDIT
                        subreddit to query (default: AmItheAsshole)
  --sample              sample complete date range up to limit, rather than
                        first submissions within limit
  --skip                skip all Reddit fetches; pushshift only
  -t, --throwaway-only  only throwaway accounts ('throw' and 'away') get
                        fetched from Reddit
  -L, --log-to-file     log to file reddit-query.log
  -V, --verbose         increase verbosity from critical though error,
                        warning, info, and debug
  --version             show program's version number and exit
```

## reddit-watch

```
usage: reddit-watch [-h] [-i INIT] [--hours HOURS] [-L] [-V] [--version]

Watch the deletion/removal status of Reddit messages. Initialize subreddits to
be watched first (e.g., 'Advice+AmItheAsshole). Schedule using cron or launchd

options:
  -h, --help         show this help message and exit
  -i, --init INIT    INITIALIZE `+` delimited subreddits to watch
  --hours HOURS      previous HOURS to fetch
  -L, --log-to-file  log to file reddit-watch.log
  -V, --verbose      increase verbosity from critical though error, warning,
                     info, and debug
  --version          show program's version number and exit
```

## reddit-message

```
usage: reddit-message [-h] -i FILENAME [-a FILENAME] [-g FILENAME] [-d] [-e]
                      [-p] [-t] [-r RATE_LIMIT] [-s] [-D] [-L] [-V]
                      [--version]

Message Redditors using CSV files with usernames in column `author_p`. Can
take output of reddit-query or reddit-watch and select users for messaging
based on attributes.

options:
  -h, --help            show this help message and exit
  -i, --input-fn FILENAME
                        CSV filename, with usernames, created by reddit-query
  -a, --archive-fn FILENAME
                        CSV filename of previously messaged users to skip;
                        created if doesn't exist (default: reddit-message-
                        users-past.csv)
  -g, --greeting-fn FILENAME
                        greeting message filename (default: greeting.txt)
  -d, --only-deleted    select deleted users only
  -e, --only-existent   select existent (NOT deleted) users only
  -p, --only-pseudonym  select pseudonyms only (NOT throwaway)
  -t, --only-throwaway  select throwaway accounts only ('throw' and 'away')
  -r, --rate-limit RATE_LIMIT
                        rate-limit in seconds between messages (default: 40)
  -s, --show-csv-users  also show all users from input CSV on terminal
  -D, --dry-run         list greeting and users but don't message
  -L, --log-to-file     log to file reddit-message.log
  -V, --verbose         increase verbosity from critical though error,
                        warning, info, and debug
  --version             show program's version number and exit
```

## reddit-boro-thanks

```
usage: reddit-boro-thanks [-h] [-s N] [-d DATA_DIR]

Calculate percent of BORU submissions containing thanks.

options:
  -h, --help            show this help message and exit
  -s, --sample N        print N evenly spaced examples of matching posts
  -d, --data-dir DATA_DIR
                        directory containing parquet files (default: .)
```

## reddit-demographics

```
usage: reddit-demographics [-h] [--start-year START_YEAR] [--end-year END_YEAR]
                           [--subreddits SUBREDDITS [SUBREDDITS ...]] [-v] [--cache-dir CACHE_DIR]
                           [--no-cache]
                           data_dir

Generate Reddit demographic stats table

positional arguments:
  data_dir              Directory containing parquet files

options:
  -h, --help            show this help message and exit
  --start-year START_YEAR
                        Start year (default: 2021)
  --end-year END_YEAR   End year (default: 2025)
  --subreddits SUBREDDITS [SUBREDDITS ...]
                        Subreddits to process (default: predefined list)
  -v, --verbose         Show detailed diagnostics
  --cache-dir CACHE_DIR
                        Directory to cache intermediate results (default:
                        data_dir/.demographics_cache)
  --no-cache            Ignore cached results and recompute all
```