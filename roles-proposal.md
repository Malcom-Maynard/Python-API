Written Evaluation 

1.
o first add new table to hold these different custom roles
o each tables will hold the author id's and columns for each one permissions that is required
o permissions can be easily changed by updating the values inside of the table based on the users requirements 

?Possible user SQL Create Role
2.
o the patch operation would need further code for authorization
o once  the author is authenticated the role and permissions of the user would have to check
o in this case the user has to be  as a verified author of the post, it also has to be checked to see if they are the owner of the post