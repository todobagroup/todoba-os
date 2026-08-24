#ifndef TODOBA_SYMBOL_MAPPER_MQH
#define TODOBA_SYMBOL_MAPPER_MQH


class TODOBA_SymbolMapper
{

private:

   static bool IsBrokerSymbolAvailable(
      const string symbol
   )
   {
      if(
         StringLen(
            symbol
         ) == 0
      )
      {
         return false;
      }

      bool is_custom = false;

      if(
         !SymbolExist(
            symbol,
            is_custom
         )
      )
      {
         return false;
      }

      if(is_custom)
         return false;

      return true;
   }


   static string ResolveGold()
   {
      if(
         IsBrokerSymbolAvailable(
            "GOLD.i#"
         )
      )
      {
         return "GOLD.i#";
      }

      if(
         IsBrokerSymbolAvailable(
            "GOLD"
         )
      )
      {
         return "GOLD";
      }

      if(
         IsBrokerSymbolAvailable(
            "XAUUSD"
         )
      )
      {
         return "XAUUSD";
      }

      return "";
   }


public:

   static string Resolve(
      string symbol
   )
   {
      if(
         StringLen(
            symbol
         ) == 0
      )
      {
         return "";
      }

      if(
         symbol == "XAUUSD"
         ||
         symbol == "GOLD"
      )
      {
         return ResolveGold();
      }

      if(
         IsBrokerSymbolAvailable(
            symbol
         )
      )
      {
         return symbol;
      }

      return "";
   }

};


#endif
