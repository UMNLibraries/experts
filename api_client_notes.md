# API Client notes

* request many serially
  * request function that takes only next token (partially applied)
  * function to get next token from current response
* request many concurrently
  * request function that takes only an offset, record id, etc (partially applied)
  * function that provides all offsets, ids, etc
  
# Scopus (also Pure?) API support group at Elsevier

* https://service.elsevier.com/app/contact/supporthub/dataasaservice/  
