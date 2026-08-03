#ifndef TODOBA_SYMBOL_MAPPER_MQH
#define TODOBA_SYMBOL_MAPPER_MQH


class TODOBA_SymbolMapper
{

public:

   static string Resolve(
      string symbol
   )
   {

      if(
         symbol == "XAUUSD"
      )
      {
         return "GOLD.i#";
      }


      if(
         symbol == "GOLD"
      )
      {
         return "GOLD.i#";
      }


      return symbol;
   }

};


#endif