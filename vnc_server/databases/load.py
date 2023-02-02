from neodb import NeoDB

mydb = NeoDB()

response = mydb.deleteEverytyhing()
if (response.success != True):
	print('Failed to delete everything: %s' % response.message)
	exit()

response = mydb.loadGraph("../neo_util/mygraph.gen.json")
print(response.message)

