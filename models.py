import keras.engine.data_adapter
import numpy as np
from tensorflow.keras import layers, Model, losses, metrics, regularizers, activations, backend
from keras.engine import data_adapter
import tensorflow as tf



def identity_block(x, filter, activation):
    # copy tensor to variable called x_skip
    x_skip = x
    # Layer 1
    x = layers.Conv1D(filter, 3, activation=activation, padding='same')(x)
    x = layers.BatchNormalization(axis=2)(x)
    x = layers.Activation(activation=activation)(x)
    # Layer 2
    x = layers.Conv1D(filter, 3, activation=activation, padding='same')(x)
    x = layers.BatchNormalization(axis=2)(x)
    # Add Residue
    x = layers.Add()([x, x_skip])
    x = layers.Activation(activation=activation)(x)
    return x


def convolutional_block(x, filter, activation):
    # copy tensor to variable called x_skip
    x_skip = x
    # Layer 1
    x = layers.Conv1D(filter, 3, activation=activation, padding='same', strides=2)(x)
    x = layers.BatchNormalization(axis=2)(x)
    x = layers.Activation(activation=activation)(x)
    # Layer 2
    x = layers.Conv1D(filter, 3, activation=activation, padding='same')(x)
    x = layers.BatchNormalization(axis=2)(x)
    # Processing Residue with conv(1,1)
    x_skip = layers.Conv1D(filter, 1, activation=activation, strides=2)(x_skip)
    # Add Residue
    x = layers.Add()([x, x_skip])
    x = layers.Activation(activation=activation)(x)

    return x


def resnet(activation, optimizer, input_shape, frames):
    # Step 1 (Setup Input Layer)
    x_input = layers.Input(shape=(frames, input_shape, 4), name="input")
    x = layers.ZeroPadding2D((0, 3))(x_input)
    # Step 2 (Initial Conv layer along with maxPool)
    x = layers.Conv2D(64, (frames, 7), strides=(1, 2), activation='tanh', padding='same')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation(activation=activation)(x)
    x = layers.Reshape((int((input_shape+6)/2), 64))(x)
    x = layers.Conv1D(64, 1, activation=activation)(x)
    x = layers.MaxPool1D(3, strides=2, padding='same')(x)
    # Define size of sub-blocks and initial filter size
    block_layers = [3, 4, 6, 3]
    filter_size = 64
    # Step 3 Add the Resnet Blocks
    for i in range(4):
        if i == 0:
            # For sub-block 1 Residual/Convolutional block not needed
            for j in range(block_layers[i]):
                x = identity_block(x, filter_size, activation=activation)
        else:
            # One Residual/Convolutional Block followed by Identity blocks
            # The filter size will go on increasing by a factor of 2
            filter_size = filter_size * 2
            x = convolutional_block(x, filter_size, activation=activation)
            for j in range(block_layers[i] - 1):
                x = identity_block(x, filter_size, activation=activation)
    # Step 4 End Dense Network
    x = layers.AveragePooling1D(2, padding='same')(x)
    x = layers.Flatten()(x)
    x = layers.Dense(512, activation=activation, kernel_regularizer=regularizers.l2(0.001))(x)
    x = layers.Dense(input_shape*2, activation=activations.linear, kernel_regularizer=regularizers.l2(0.001))(x)
    x = layers.Reshape((input_shape, 2))(x)
    model = Model(x_input, x)
    # print(model.summary())

    stringlist = []
    model.summary(print_fn=lambda x: stringlist.append(x))
    sum = "\n".join(stringlist)

    # model = Custom_Model.CustomModel(model)
    # model.compile(optimizer=optimizer)

    metric = metrics.MeanAbsoluteError(name="MAE")
    model.compile(optimizer=optimizer, loss=losses.MeanSquaredError(), metrics=[metric], )
    return [model, sum]


def residual_cell(x, activation, layer_size=2, size=10):
    x_skip = x
    for i in range(layer_size):
        x = layers.Dense(size, activation=activation)(x)
    input_size = x_skip.get_shape()[1]
    x = layers.Dense(input_size, activation=activation)(x)
    x = layers.Add()([x, x_skip])
    x = layers.Activation(activation=activation)(x)
    return x


def message_model(frames, input_number, output_number, activation, residual_cells=None):
    if residual_cells is None:
        residual_cells = [[2, 10], [2, 10], [2, 10], [2, 10], [2, 10], [2, 10]]
    x_input = layers.Input(shape=(frames, input_number), name="message_input")
    x = layers.Flatten()(x_input)
    for cell_struct in residual_cells:
        x = residual_cell(x, activation, layer_size=cell_struct[0], size=cell_struct[1])
        x = layers.Dropout(0.04)(x)
    x = layers.Dense(output_number, activation=activation)(x)
    model = Model(x_input, x)
    return model


def interpretation_model(input_number, output_number, activation, residual_cells=None):
    if residual_cells is None:
        residual_cells = [[2, 20], [2, 20], [2, 20], [2, 20], [2, 20], [2, 20]]
    x_input = layers.Input(shape=input_number, name="interpretation_input")
    x = layers.Dense(30, activation=activation)(x_input)
    for cell_struct in residual_cells:
        x = residual_cell(x, activation, layer_size=cell_struct[0], size=cell_struct[1])
        x = layers.Dropout(0.04)(x)
    x = layers.Dense(output_number, activation=activations.linear)(x)
    model = Model(x_input, x)
    return model


def graph_network(frames, activation, m_input, m_output, i_output, optimiser):
    m_model = message_model(frames, m_input, m_output, activation)
    m_model.compile(run_eagerly=True)
    i_model = interpretation_model(m_output+4, i_output, activation)
    i_model.compile(run_eagerly=True)
    model = CustomModel(m_model, i_model, m_output)
    model.compile(run_eagerly=True, optimizer=optimiser)
    return model


class CustomModel(Model):
    mse = metrics.MeanSquaredError(name="MSE")

    def loss_function(self, y_true, y_pred):
        loss = losses.mean_squared_error(y_true, y_pred)
        return loss

    def __init__(self, m_model, i_model, m_model_output):
        super(CustomModel, self).__init__()
        self.m_model = m_model
        self.m_model_output = m_model_output
        self.i_model = i_model

    # @tf.function
    def call(self, inputs, training=None, mask=None):
        return 1

    def call_2(self, input_data):
        batch_prediction = []
        shape = input_data.shape
        for batch_number in range(shape[0]):
            message_array = []
            col_index = 0

            for col_number in range(shape[1]):
                placeholder_data = tf.concat([input_data[batch_number, :, :, :4],
                                              input_data[batch_number, :, :, col_number + 4:col_number + 5]],
                                             axis=2)
                messages = self.m_model(placeholder_data, training=False)
                message_sum = backend.sum(messages, axis=0)
                message_sum = tf.concat(
                    [message_sum, tf.cast(input_data[batch_number, col_number, -1, :4], tf.float32)], 0)
                # message_sum = tf.expand_dims(message_sum, 0)
                message_array.append(message_sum)
                col_index += 1
            message_array = tf.stack(message_array)
            batch_prediction.append(self.i_model(message_array, training=False))
        return tf.stack(batch_prediction)

    @tf.function
    def train_step(self, data):
        input_data, y, sample_weight = data_adapter.unpack_x_y_sample_weight(data)

        with tf.GradientTape(persistent=False, watch_accessed_variables=False) as tape_1:
            tape_1.watch(self.i_model.trainable_variables)
            tape_1.watch(self.m_model.trainable_variables)

            batch_prediction = []
            shape = input_data.shape
            for batch_number in range(shape[0]):
                message_array = []
                col_index = 0

                for col_number in range(shape[1]):
                    placeholder_data = tf.concat([input_data[batch_number, :, :, :4],
                                                  input_data[batch_number, :, :, col_number + 4:col_number + 5]],
                                                 axis=2)
                    messages = self.m_model(placeholder_data, training=True)
                    message_sum = backend.sum(messages, axis=0)
                    message_sum = tf.concat(
                        [message_sum, tf.cast(input_data[batch_number, col_number, -1, :4], tf.float32)], 0)
                    # message_sum = tf.expand_dims(message_sum, 0)
                    message_array.append(message_sum)
                    col_index += 1
                message_array = tf.stack(message_array)
                batch_prediction.append(self.i_model(message_array, training=True))
            y_pred = tf.stack(batch_prediction)
            loss_tot = losses.mean_squared_error(y, y_pred)
        self.optimizer.minimize(loss_tot, [self.i_model.trainable_variables, self.m_model.trainable_variables], tape=tape_1)
        return {"MSE": loss_tot}

    def test_step(self, data):
        x, y, sample_weight = data_adapter.unpack_x_y_sample_weight(data)
        # y_pred = self(x, training=False)
        # self.mse.update_state(y, y_pred)
        # mse_result = self.mse.result()
        return {"MSE": 1}