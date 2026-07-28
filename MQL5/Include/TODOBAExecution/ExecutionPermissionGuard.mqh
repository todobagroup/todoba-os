#ifndef TODOBA_EXECUTION_PERMISSION_GUARD_MQH
#define TODOBA_EXECUTION_PERMISSION_GUARD_MQH


class TODOBAExecutionPermissionGuard
{
private:

   static int last_sequence;


public:

   static bool Allow(
      const int sequence
   )
   {
      if(sequence <= 0)
         return false;

      if(sequence <= last_sequence)
         return false;

      last_sequence = sequence;

      return true;
   }


   static int LastSequence()
   {
      return last_sequence;
   }
};


int TODOBAExecutionPermissionGuard::last_sequence = 0;


#endif