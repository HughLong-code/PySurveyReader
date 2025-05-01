# SurveyReader class and its associated functions provide read from Qualtrics and write to Snowflake functionality

---

## Installation:
  ```shell
  pip install PySurveyReader
  ```

## Classes:

### `SurveyReader`
A class to handle reading and processing survey files from Qualtrics.

---

## SurveyReader Methods:

### `SurveyReader()`
Initializes the SurveyReader instance with the given file path or auth arguments - but not both.

**Keyword Parameters:**
- `pathToFile (str)`  
  The file path to read the Qualtrics credentials from. Expects credentials in JSON format adhering to the following schema:  
  `{"client_id" : "urID", "client_secret" : "urSecret", "datacenter" : "urdatacenter", "survey_id" : "ursurveyId"}`

- `dataCenter (str)`  
  You may specify the datacenter ID.

- `clientId (str)`  
  The client ID for Qualtrics client.

- `clientSecret (str)`  
  The client secret for Qualtrics OAuth.

- `surveyId (str)`  
  The ID for your survey. If you do not want to specify this in a config file, you can leave it out and specify it on object creation as a passed value.  
  This is not the case with the other config params (secret, ID, etc.).  
  The survey ID is found in the URL to your survey, e.g., when viewing your survey with URL:  
  `https://foo.yul1.qualtrics.com/survey-builder/SWECCNSJKJK!!@##/edit`,  
  the ID would be `SWECCNSJKJK!!@##` (this isn't a real ID, btw).

- `subDirTarget (str)`  
  The directory to write the temp files created during survey decompression into a dataframe. Defaults to the current working directory.

- `altBaseURL (str)`  
  Specify an alternate base URL for Auth API requests. Current default is:  
  `https://urdatacenter.qualtrics.com/oauth2/token`

- `altAPIURL (str)`  
  Specify an alternate base URL for API requests. Current default is:  
  `https://yourdatacenter.qualtrics.com/API`

- `altExportURL (str)`  
  Specify an alternate export URL path to add to the APIURL. Current default is:  
  `/v3/surveys/ursurveyID/export-responses`

---

### `read() -> self`
Reads the survey data file from Qualtrics and loads its content into memory.

**Keyword Parameters:**
- `includeLabels (bool)`  
  Whether or not to export label columns from Qualtrics or only recode values.

- `secondsToWait (int)`  
  An integer representing how long to wait for the file download to succeed before terminating with an error. Default: 2 minutes.

---

### `to_df() -> dict`
Returns the previously read `SurveyReader` object as a dictionary with the name as the key and the value as a pandas dataframe holding the survey responses.

**Keyword Parameters:**
- `dropHeaders (bool)`  
  Whether to drop the extra headers Qualtrics typically sends. If true, will drop the first and second rows of the dataframe.

- `keepFile (bool)`  
  Whether to keep the CSV file created when the bytestring is decompressed.  
  The file will be written to the current working directory if `subDirTarget` was not specified on object creation.

- `makeLong (bool)`  
  Whether to make the dataframe into a long format dataframe, this will split it into 3 dataframes all joinable together that hold `responses`, `question text` and `metadata`. Will keep question headers from being limited to 250 charachters. The dataframes will be retuned as a nested dict under the original survey name as the key. The keys for the dfs will be `responses` , `metadata` and `question_text`.

- `fsuidColumn (bool)`  
  If set to True, expects a column called `FSUID` to be in the survey beyond standard qualtrics metadata columns - will throw error if set to true and column `FSUID` is not present.

---

## Functions:

### `read_sql() -> pd.DataFrame`
Returns the result of some arbitrary SQL executed by the Snowflake cursor passed in as a pandas dataframe.

**Keyword Parameters:**
- `cur (snowflake.connector.cursor)`  
  The Snowflake cursor object to use.

- `sql (str)`  
  The string containing the SQL you wish to execute.

---

### `to_snowflake() -> int`
Writes a dataframe to Snowflake. Can also write only those rows that have not been written to a table sharing the same name as `tableName` based on key columns specified.  
The column's values will be compared as strings, and only rows containing non-duplicated values will be written.  
Returns the number of rows written upon success.

**Keyword Parameters:**
- `conn (str)`  
  The Snowflake connection you want to use. Be sure to specify a target schema when you create it.

- `df (pd.DataFrame)`  
  The dataframe you want to migrate to Snowflake.

- `overwrite (bool)`  
  Whether or not to overwrite (truncate) an existing table.

- `createTable (bool)`  
  Whether or not to create a table if it does not exist.  
  If set to `True` with `overwrite`, will drop and recreate the target table.

- `onlyPushNew (bool)`  
  Whether to only push new content based on a set of ID columns to Snowflake.  
  If set to `True`, you **MUST** specify Snowflake ID and dataframe ID columns.

- `snowflakeIdColumn (str)`  
  The column name for the table in Snowflake to use as the comparison when deciding if a row is new or not.

- `dfIdColumn (str)`  
  The column name for the column you want to use as the ID column in the passed dataframe.  
  Will be used to compare with the Snowflake ID column to determine which rows are new and should be pushed.

---

## Usage:

```python
a = surveyReader.SurveyReader(pathToFile='C:/some/path/to/qualtrics_cred.json', surveyId='someid78934759')

x = a.read().to_df()

df = x['somename']

to_snowflake(conn, df, 'somename')
```


### Credential Format:

You may specify the credentials needed as named parameters upon initializing a member of SurveyReader, or you can include a path to a .env or .json file with the credentials in the format:

```json
{
  "client_id": "urID",
  "client_secret": "urSecret",
  "datacenter": "urdatacenter",
  "survey_id": "ursurveyId"
}
```

### long survery option:

When calling `to_df()` on an object you may specify that you want the survey results in long format. This will create 3 tables holing response metadata (time, ip address, fsuid (if it exists)) , responses themselves and the question head text itself respectively. These will be returned as a nested dict under the key of the survey name in the returned object. It will follow the following format in this case.

```python
{
  'somesurveyname' :
  {
    'responses' : pd.Dataframe(),
    'metadata' : pd.Dataframe(),
    'question_text' : pd.dataframe()
  }

}
```

### Notes:

As previously stated, you can specify a survey id in a config file OR as a parameter passed at object creation - don't do both. This is done as you may want to fire off multiple survey reads one after another in something like a loop using the same credentials, this will allow you to do that. Don't specify other credentials ( including datacenter id ) in a config file AND as params - it's bad practice, and will throw an error. 

you may be unfarmiliar with the syntax for creating a snowflake connection object to pass to a method like to_snowflake() , this snippet should help you along. Note that you need to specify which schema you want to write to in the connection object you pass for to_snowflake() to work properly. 

This snippet assumes a system level account that doesn't need SAML auth.

```python
import snowflake.connector

conn = snowflake.connector.connect(
    user="username", 
    password = 'password',
    account="account",
    warehouse="warehouse_to_use",
    database="database",
    role='theroletouse',
    schema='schematouse' # Change to fit whatever schema you want
)

#then just pass the conn object to to_snowflake() , the function will write your df to whatever schema was specified in the 'schema' param
```

This snippet uses SAML auth

```python
import snowflake.connector

conn = snowflake.connector.connect(
    user="uremail@somedomain.com", # Email goes here
    authenticator="externalbrowser", # Uses SSO login
    account="uraccount",
    warehouse="urwarehouse",
    role = "roletouse",
    database="urdatabase",
    schema='urschema' # Change to fit whatever schema you want
)

#this snippet will pull up a browser window for Oauth - it is more secure than a method using username/password and should be used where practicable.
```
