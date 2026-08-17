#ifndef TODOBA_CONTROL_PERMISSION_GUARD_MQH
#define TODOBA_CONTROL_PERMISSION_GUARD_MQH


class TODOBAControlPermissionGuard
{
private:

   static long last_sequence;


public:

   static bool Check(
      const long sequence
   )
   {
      if(sequence <= 0)
         return false;

      if(sequence <= last_sequence)
         return false;

      return true;
   }


   static bool Commit(
      const long sequence
   )
   {
      if(
         !Check(
            sequence
         )
      )
      {
         return false;
      }

      last_sequence = sequence;

      return true;
   }


   static long LastSequence()
   {
      return last_sequence;
   }
};


long TODOBAControlPermissionGuard::last_sequence = 0;


#endif