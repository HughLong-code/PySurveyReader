Classes:
    SurveyReader:
        A class to handle reading and processing survey files from qualtrics.

SurveyReader() Methods:
    SurveyReader()
        Initializes the SurveyReader instance with the given file path or arguments - but not both.

        Keyword Parameters:
        -
        pathToFile (str) : The file path to read the qualtrics credentials from. Expects crediantials in JSON format adhering to the folowing schema '{"client_id" : "urID" , "client_secret" : "urSecret" , "datacenter" : "urdatacenter" , "survey_id" : "ursurveyId"}'.
        
        dataCenter (str) : you may specify the datacenter id.
        
        clientId (str) : the client id for qualtrics client.
        
        clientSecret (str) : the cleint secret for qualtrics Oauth.
        
        surveyId (str) : the id for your survey. If you do not want to specify this in a config file you can leave it out and specify it on object creation as a passed value. This is not the case with the other config params - secret, id, etc.. the survey ID is found in the url to your survey i.e. in when viewing your survey with url https://foo.yul1.qualtrics.com/survey-builder/SWECCNSJKJK!!@##/edit , the id would be 'SWECCNSJKJK!!@##' (this isnt a real id btw)
        
        subDirTarget (str) : The directory to write the temp files created during survey decompression into a dataframe, defaults to current working directory.
        
        altBaseURL (str) : Specify an alternate base url for Auth API requests. Current default is - https://urdatacenter.qualtrics.com/oauth2/token

        altAPIURL (str) : Specify an alternate base url for API requests. Current default is - https://yourdatacenter.qualtrics.com/API

        altExportURL (str) : Specify an alternate export url path to add to the APIURL. Current default is - /v3/surveys/ursurveyID/export-responses

    read() -> self:
        Reads the survey data file from qualtrics and loads its content into memory.

        Keyword Parameters:
        -
        includeLabels (bool) : whether or not to export label columns from qualtrics or only recode values.
        
        secondsToWait (int) : An int representing how long to wait for the file download to succeed before terminating with an error, default 2 minutes.

    to_df() -> dict

        returns the previously read SurveyReader object as a dictionary with the name as the key and the value as a pandas dataframe holding the survey responses.

        Keyword Parameters:
        -
        dropHeaders (bool) : whether to drop the extra headers qualtrics typically sends. If true will drop the first and second rows of the df.
        
        keepFile (bool) : Whether to keep the csv file created when the bytestring is decompressed. File will be written to the current working directory if 'subDirTarget' was not specified on object creation.


Functions:

    read_sql()->pd.dataframe

        Returns the result of some arbitrary sql executed by the snowflake cursor passed in as a pandas dataframe

        Keyword Parameters:
        -
        cur (snowflake.connector.cursor) : the snowflake cursor object to use.
        
        sql (str) : the string containing the sql you wish to execute


    to_snowflake() -> int

        Writes a dataframe to snowflake, can also write only those rows that have not been written to a table sharing the same name as tableName based on key columns specified, the column's values will be compared as strings and only rows containing non-duplicated values will be written.

        Keyword Parameters:
        -
        conn (str) : the snowflake connection you want to use, be sure to specify a target schema when you create it.

        df (pd.Dataframe) : the dataframe you want to migrate to snowflake.

        overwrite (bool) : whether or not to overwrite (truncate) an existing table.

        createTable (bool) : whether or not to create a table if it does not exist, if set to True with overwrite - will drop and recreate target table.

        onlyPushNew (bool) : whether to only push new content based on a set of id columns to snowflake. If set to true you MUST specify snowflake id and df id columns.

        snowflakeIdColumn (str) : the column name for the table in snowflake to use as the comparison when deciding if a row is new or not.

        dfIdColumn (str) : the column name for the column you want to use as the id column in the passed dataframe. Will be used to compare with snowflake id column to determine which rows are new and should be pushed.


Usage:
    a = surveyReader.surveyReader(pathToFile='C:/some/path/to/qualtrics_cred.json' , surveyId='someid78934759')

    x = a.read().to_df()

    df = x['somename]

    to_snowflake(conn , df , 'somename')
"""
