import json
from django.db import transaction

from django.http import HttpResponse, Http404, JsonResponse
import random
from backend_api.DBdriver import *

from backend_api.models import *
from django.shortcuts import get_object_or_404
from collections import defaultdict

# Method that clears the Database
def clearDB(request):
    System.objects.all().delete()
    Attribute.objects.all().delete()
    Relationship.objects.all().delete()
    print('DB cleared')
    return HttpResponse()

# Create your views here.
def handle(request):
    return HttpResponse("Home Page")

# Method that takes the input data through json request
@transaction.atomic
def BNYBackEndPost(request):
    if request.method != 'POST' or not request.POST.get('JsonData'):
        raise Http404
    jsonString = request.POST['JsonData']
    jsonObj = json.loads(jsonString)
    # {'source': 's1name', 'destination': 's2name', 'fields': ['fname1', 'fname2']}
    # print(jsonObj)
    try:
        sourceName  = jsonObj['source']
        destName = jsonObj['destination']
        fields = jsonObj['fields']
    except:
        return JsonResponse({"error":"field missing or check spell"},status=400)

    try:
        handleJson(jsonObj)
        return HttpResponse(status=200)
    except:
        return JsonResponse({"error":"field missing or check spell"},status=400)


# Method that handles the input through file upload
def fileUpload(request):
    if request.method != 'POST' or 'csv_file' not in request.FILES:
        return JsonResponse({"error":"csv_file parameter missing in POST request"},status=400)
    csv_file = request.FILES['csv_file']
    if not csv_file.name.endswith('.csv'):
        return JsonResponse({"error":"Only .csv files are allowed"},status=400)
    file_data = csv_file.read().decode("utf-8") 
    lines = file_data.split("\n")
    for line in lines[1:]:
        cols = line.strip().split(',')
        if len(cols) < 2: continue
        jsonObj = {}
        jsonObj['source'] = cols[0]
        jsonObj['destination'] = cols[1]
        jsonObj['fields'] = list()
        for i in range(2, len(cols)):
            if cols[i].strip() != "":
                jsonObj['fields'].append(cols[i])
        handleJson(jsonObj)
    return HttpResponse(status=200)

# Method that returns a JSON string representing Overlaps
def getOverlaps(request):
    result = {}
    overlaps = []
    for dest in Relationship.objects.values_list("toSystem_id",flat=True).distinct():
        destName = get_object_or_404(System, id=dest).name
        sources = Relationship.objects.filter(toSystem_id=dest)
        seen = set()

        for i in range(len(sources)):
            # print (sources[i].fromSystem.name)
            # fields involves message from i to dest
            relation1 =get_object_or_404(Relationship, toSystem_id=dest, fromSystem_id=sources[i].fromSystem.id)
            # print (relation1.attributes.all())
            for j in range(i + 1, len(sources)):
                # fields involves message from j to dest
                relation2 = get_object_or_404(Relationship, toSystem_id=dest, fromSystem_id=sources[j].fromSystem.id)
                # find intersect if any
                intersect = list(set(relation1.attributes.all()) & set(relation2.attributes.all()))

                

                # if intersect detected
                if len(intersect) > 0:
                    for field in intersect:
                        innerObj = {}
                        innerObj['field'] = field.name
                        innerObj['dest'] = destName
                        innerObj['sources'] = sources[i].fromSystem.name
                        string = innerObj['field'] + innerObj['dest'] + innerObj['sources']
                        if string not in seen:
                            overlaps.append(innerObj)
                            seen.add(string)
                        innerObj = {}
                        innerObj['field'] = field.name
                        innerObj['dest'] = destName
                        innerObj['sources'] = sources[j].fromSystem.name
                        string = innerObj['field'] + innerObj['dest'] + innerObj['sources']
                        if string not in seen:
                            overlaps.append(innerObj)
                            seen.add(string)
    result['overlaps'] = overlaps    
    return JsonResponse(result, status=200)

# Method that returns a JSON string representing lineage model
def getModels(request):
    result = {}
    systems = []
    result['systems'] = systems
    seen = set()
    if not System.objects.all():
        return JsonResponse(result, status=400)

    for system in System.objects.all():

        obj = {}
        innerObj = {}
        innerObj['id'] = system.name
        innerObj['color'] = system.color
        innerObj['attributes'] = []

        attributes_list = system.attributes.values_list("name", flat=True).distinct()
        for i in attributes_list:
            innerObj['attributes'].append(i)


        obj['data'] = innerObj
        obj['type'] = "node"
        systems.append(obj)

    for relation in Relationship.objects.all():
        innerObj = {}
        innerObj['source'] = relation.fromSystem.name
        innerObj['target'] = relation.toSystem.name
        innerObj['id'] = innerObj['source'] + innerObj['target']
        obj = {}
        obj['data'] = innerObj
        obj['type'] = "edge"
        systems.append(obj)

    return JsonResponse(result, status=200)

def manualProcessNode(request):
    if request.method != 'POST' or not request.POST.get('nodeName') or not request.POST.get('action'):
        return JsonResponse({'error': 'parameter missing'}, status=400)
    # user adds a new node to system
    nodeName = request.POST.get('nodeName')

    if request.POST.get('action') == 'add':
        system = System.objects.filter(name=nodeName)
        print ('aaaaaa')
        # system = get_object_or_404(System, name=nodeName)
        # system does not existed, create a new one and savew
        if not system or len(system) == 0:
            code = getColorCode()
            newSystem = System(name=nodeName, color=code)
            newSystem.save()
            # system2 = System.objects.filter(name=nodeName)
            # if system2[0]:
            #     obj = {}
            #     obj['color'] = system2[0].color
            #     return JsonResponse(obj, status=200)
            # else:
            #     return JsonResponse({'error':'failed to insert'}, status=400)
            return JsonResponse({'color': code}, status=200)
        else:
            # try to add an existed node, return 404
            return JsonResponse({'error': 'insert an existed node'}, status=400)

    if request.POST.get('action') == 'remove':
        system = System.objects.filter(name=nodeName)
        # system does existed, delete and save
        if system and len(system) > 0:
            # newSystem = System(name=nodeName)
            system[0].delete()
            return HttpResponse(status=200)
        else:
            # try to remove a non-existed node, return 404
            return HttpResponse("remove a node doesn't exist", status=400)
    # for any unexpected error, return 404
    return HttpResponse("unknown error", status=400)


def manualProcessEdge(request):
    if request.method != 'POST' or not request.POST.get('source') or not request.POST.get('destination') or not request.POST.get('action'):
        return JsonResponse({'error': 'parameter missing'}, status=400)

    source = request.POST.get('source')
    dest = request.POST.get('destination')

    sourceSystem = System.objects.filter(name=source)
    destSystem = System.objects.filter(name=dest)


    if not sourceSystem or len(sourceSystem) == 0 or not destSystem or len(destSystem) == 0:
        # try to deal with systems don't exist
        return JsonResponse({'error': 'system does not exist'}, status=400)

    relationship = Relationship.objects.filter(fromSystem_id=sourceSystem[0], toSystem_id=destSystem[0])


    if request.POST.get('action') == 'add':
        if relationship or len(relationship) > 0:
            # there is none relationship between source and dest
            return JsonResponse({'error':'this relationship has existed'},status=400)
        newR = Relationship(fromSystem=sourceSystem[0], toSystem=destSystem[0])
        newR.save()
        return HttpResponse(status=200)
    if request.POST.get('action') == 'remove':
        if not relationship:
            return JsonResponse({'error':'this relationship does not exist'},status=400)
        
        relationship[0].delete()
        return HttpResponse(status=200)


def getColorCode():
    r = lambda: random.randint(0, 255)
    color =  '#%02X%02X%02X' % (r(), r(), r())
    return color
