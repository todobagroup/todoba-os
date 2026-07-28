#property strict

#define TODOBA_AGENT_NAME "TODOBA Trusted Agent"
#define TODOBA_AGENT_VERSION "0.2.0"

input int PollIntervalSeconds = 5;
input string CloudBaseUrl = "http://127.0.0.1:8000";

void PollCloud()
{
   string url = CloudBaseUrl + "/missions/next";

   char request_body[];
   char response_body[];

   string response_headers;

   ResetLastError();

   int status_code = WebRequest(
      "GET",
      url,
      "",
      3000,
      request_body,
      response_body,
      response_headers
   );

   if(status_code == -1)
   {
      Print(
         "TODOBA Trusted Agent: cloud request failed. error=",
         GetLastError()
      );

      return;
   }

   string response = CharArrayToString(
      response_body
   );

   Print(
      "TODOBA Trusted Agent: cloud status=",
      status_code,
      " response=",
      response
   );
}


int OnInit()
{
   if(PollIntervalSeconds < 1)
   {
      Print(
         "TODOBA Trusted Agent: invalid poll interval."
      );

      return(INIT_PARAMETERS_INCORRECT);
   }

   if(StringLen(CloudBaseUrl) == 0)
   {
      Print(
         "TODOBA Trusted Agent: cloud URL is required."
      );

      return(INIT_PARAMETERS_INCORRECT);
   }

   EventSetTimer(
      PollIntervalSeconds
   );

   Print(
      TODOBA_AGENT_NAME,
      " v",
      TODOBA_AGENT_VERSION,
      " initialized."
   );

   return(INIT_SUCCEEDED);
}


void OnDeinit(const int reason)
{
   EventKillTimer();

   Print(
      TODOBA_AGENT_NAME,
      " stopped. reason=",
      reason
   );
}


void OnTimer()
{
   PollCloud();
}