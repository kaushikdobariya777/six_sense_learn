from apps.classif_ai.service.metrics_service import ClasswiseMetrics, ConfusionMatrix

### modularity or speed ?
# to maintain MODULARITY, data retrieval and data calculation can be separated
# service classes aim to get data whereas metrics classes use the obtained data to calculate metrics
# could be particularly helpful in cases where same data could be used for multiple calculation

# we could go for SPEEDY results by letting sql do the calculation so we directly get the metrics
# metrics classes could do the complex sql and service classes could simply be a mediator

### why the static methods?
# no benefit of creating metrics object, hence the static method call
# we create a object so that it can be reused in the code
# but chances that same metric type will be asked in single API call is very low
# and using same object across multiple API call(shared resources) is risky


def get_classwise_metrics(request):
    return ClasswiseMetrics.get_classwise_metrics()


def get_confusion_matrix(request):
    return ConfusionMatrix.get_confusion_matrix()


def get_confusion_matrix_with_relative_strength(request):
    return ConfusionMatrix.get_confusion_matrix_with_relative_strength()
