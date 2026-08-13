#ifndef TODOBA_ACCOUNT_FINGERPRINT_MQH
#define TODOBA_ACCOUNT_FINGERPRINT_MQH


class TODOBAAccountFingerprint
{
public:

   static string Build()
   {
      string server = AccountInfoString(
         ACCOUNT_SERVER
      );

      long login = AccountInfoInteger(
         ACCOUNT_LOGIN
      );

      if(StringLen(server) == 0)
         return "";

      if(login <= 0)
         return "";

      return (
         server
         + ":"
         + IntegerToString(
            login
         )
      );
   }
};


#endif