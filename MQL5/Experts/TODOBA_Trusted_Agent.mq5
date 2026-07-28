#property strict

#define TODOBA_AGENT_NAME "TODOBA Trusted Agent"
#define TODOBA_AGENT_VERSION "0.1.0"

input int PollIntervalSeconds = 5;

int OnInit()
{
   if(PollIntervalSeconds < 1)
   {
      Print("TODOBA Trusted Agent: invalid poll interval.");
      return(INIT_PARAMETERS_INCORRECT);
   }

   EventSetTimer(PollIntervalSeconds);

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
   Print("TODOBA Trusted Agent: poll tick.");
}